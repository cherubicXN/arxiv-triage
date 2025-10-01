from fastapi import APIRouter, Depends, Query, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from typing import List, Optional
from ..db import get_session
from ..models import Paper, Action, PaperState
from ..schemas import (
    PapersResponse,
    PaperOut,
    SetStateReq,
    TagsReq,
    PapersStats,
    BatchScoreReq,
    BatchScoreResp,
    PapersHistogram,
    RubricSetReq,
    RubricScores,
)
from ..services.scoring import search_bm25
from ..services.llm import llm_rubric_score, llm_suggest_tags

router = APIRouter(tags=["papers"])

@router.get("/papers", response_model=PapersResponse)
async def list_papers(
    state: Optional[str] = Query(None),
    query: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session)
):
    stmt = select(Paper)
    if state:
        stmt = stmt.where(Paper.state == state)
    # Default ordering: arXiv id (desc) then version (desc)
    stmt = stmt.order_by(Paper.arxiv_id.desc(), Paper.version.desc())
    res = await session.execute(stmt)
    rows = res.scalars().all()

    if query:
        # naive BM25 over title+abstract in-memory
        docs = [(p.id, f"{p.title} {p.abstract}") for p in rows]
        ranked_ids = search_bm25(docs, query)
        id_to_p = {p.id: p for p in rows}
        rows = [id_to_p[i] for i in ranked_ids if i in id_to_p]

    total = len(rows)
    start = (page - 1) * page_size
    end = start + page_size
    rows = rows[start:end]
    return {"ok": True, "data": [PaperOut.model_validate(r) for r in rows], "total": total}

@router.get("/papers/stats", response_model=PapersStats)
async def papers_stats(
    state: Optional[str] = Query(None),
    query: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_session)
):
    """
    Global counts for categories and tags across the (optionally filtered) dataset.
    - Respects `state` filter.
    - If `query` provided, applies BM25 over title+abstract and computes counts over matched set.
    """
    stmt = select(Paper)
    if state:
        stmt = stmt.where(Paper.state == state)
    # Base order doesn't matter for stats; reuse deterministic ordering
    stmt = stmt.order_by(Paper.arxiv_id.desc(), Paper.version.desc())
    res = await session.execute(stmt)
    rows = res.scalars().all()

    if query:
        docs = [(p.id, f"{p.title} {p.abstract}") for p in rows]
        ranked_ids = set(search_bm25(docs, query))
        rows = [p for p in rows if p.id in ranked_ids]

    total = len(rows)
    # Category counts (by primary_category)
    cat_counts: dict[str, int] = {}
    tag_counts: dict[str, int] = {}
    empty_tag_count = 0
    for p in rows:
        cat = (p.primary_category or "unknown").strip() or "unknown"
        cat_counts[cat] = cat_counts.get(cat, 0) + 1
        tag_list = (p.tags or {}).get("list", []) or []
        if not tag_list:
            empty_tag_count += 1
        for t in tag_list:
            t = (t or "").strip()
            if not t:
                continue
            tag_counts[t] = tag_counts.get(t, 0) + 1

    return {
        "ok": True,
        "total": total,
        "categories": cat_counts,
        "tags": tag_counts,
        "empty_tag_count": empty_tag_count,
    }

@router.post("/papers/{paper_id}/score")
async def score_paper(
    paper_id: int,
    provider: str | None = Query(None, description="LLM provider: openai|deepseek"),
    session: AsyncSession = Depends(get_session),
):
    res = await session.execute(select(Paper).where(Paper.id == paper_id))
    paper = res.scalar_one_or_none()
    if not paper:
        raise HTTPException(404, "paper not found")
    scores = llm_rubric_score(paper.title or "", paper.abstract or "", provider=provider)
    sig = dict(paper.signals or {})
    sig["rubric"] = scores
    paper.signals = sig
    session.add(paper)
    await session.commit()
    return {"ok": True, "data": {"paper_id": paper_id, "rubric": scores}}

@router.post("/papers/{paper_id}/suggest-tags")
async def suggest_tags(
    paper_id: int,
    provider: str | None = Query(None, description="LLM provider: openai|deepseek"),
    session: AsyncSession = Depends(get_session),
):
    res = await session.execute(select(Paper).where(Paper.id == paper_id))
    paper = res.scalar_one_or_none()
    if not paper:
        raise HTTPException(404, "paper not found")
    suggestions = llm_suggest_tags(paper.title or "", paper.abstract or "", paper.categories or "", provider)
    sig = dict(paper.signals or {})
    sig["suggested_tags"] = suggestions
    paper.signals = sig
    session.add(paper)
    await session.commit()
    return {"ok": True, "data": {"paper_id": paper_id, "suggested": suggestions}}

@router.post("/papers/{paper_id}/rubric", response_model=dict)
async def set_rubric(
    paper_id: int,
    body: RubricSetReq = Body(...),
    session: AsyncSession = Depends(get_session),
):
    res = await session.execute(select(Paper).where(Paper.id == paper_id))
    paper = res.scalar_one_or_none()
    if not paper:
        raise HTTPException(404, "paper not found")
    # sanitize values to 1..5
    def clamp(x: int) -> int:
        return max(1, min(5, int(x)))
    scores = {
        "novelty": clamp(body.novelty),
        "evidence": clamp(body.evidence),
        "clarity": clamp(body.clarity),
        "reusability": clamp(body.reusability),
        "fit": clamp(body.fit),
    }
    scores["total"] = int(body.total) if body.total is not None else sum(scores.values())
    sig = dict(paper.signals or {})
    sig["rubric"] = scores
    paper.signals = sig
    session.add(paper)
    await session.commit()
    return {"ok": True, "data": {"paper_id": paper_id, "rubric": scores}}

@router.get("/papers/histogram_by_day", response_model=PapersHistogram)
async def histogram_by_day(
    state: Optional[str] = Query(None),
    query: Optional[str] = Query(None),
    month: Optional[str] = Query(None, description="YYYY-MM; if missing, last 31 days"),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Paper)
    if state:
        stmt = stmt.where(Paper.state == state)
    stmt = stmt.order_by(Paper.arxiv_id.desc(), Paper.version.desc())
    res = await session.execute(stmt)
    rows = res.scalars().all()

    if query:
        docs = [(p.id, f"{p.title} {p.abstract}") for p in rows]
        matched = set(search_bm25(docs, query))
        rows = [p for p in rows if p.id in matched]

    from datetime import datetime, timezone, timedelta
    counts: dict[str, int] = {}
    if month:
        # filter to year-month prefix
        for p in rows:
            day = None
            if p.submitted_at and p.submitted_at.startswith(month):
                day = p.submitted_at[:10]
            elif p.updated_at and p.updated_at.startswith(month):
                day = p.updated_at[:10]
            if day:
                counts[day] = counts.get(day, 0) + 1
    else:
        # last 31 days window
        today = datetime.now(timezone.utc).date()
        cutoff = today - timedelta(days=31)
        def _to_date(s: Optional[str]):
            try:
                return datetime.fromisoformat(s).date() if s else None
            except Exception:
                return None
        for p in rows:
            d = _to_date(p.submitted_at) or _to_date(p.updated_at)
            if d and d >= cutoff:
                day = d.isoformat()
                counts[day] = counts.get(day, 0) + 1

    return {"ok": True, "counts": counts}

@router.post("/papers/score-batch", response_model=BatchScoreResp)
async def score_batch(body: BatchScoreReq = Body(...), session: AsyncSession = Depends(get_session)):
    import asyncio

    # Build base query
    stmt = select(Paper)
    if body.state:
        stmt = stmt.where(Paper.state == body.state)
    stmt = stmt.order_by(Paper.arxiv_id.desc(), Paper.version.desc())
    res = await session.execute(stmt)
    rows = res.scalars().all()

    # Optional query filter via BM25
    if body.query:
        docs = [(p.id, f"{p.title} {p.abstract}") for p in rows]
        matched = set(search_bm25(docs, body.query))
        rows = [p for p in rows if p.id in matched]

    # Filter missing rubric if requested
    if body.only_missing:
        rows = [p for p in rows if not ((p.signals or {}).get("rubric"))]

    # Limit
    rows = rows[: max(0, int(body.limit))]

    scored, failed, ids = 0, 0, []
    delay = max(0, int(body.delay_ms)) / 1000.0

    for p in rows:
        try:
            # Offload potentially blocking call
            scores = await asyncio.to_thread(llm_rubric_score, p.title or "", p.abstract or "", body.provider)
            sig = dict(p.signals or {})
            sig["rubric"] = scores
            p.signals = sig
            session.add(p)
            await session.commit()
            scored += 1
            ids.append(p.id)
        except Exception:
            failed += 1
        if delay:
            await asyncio.sleep(delay)

    return {"ok": True, "scored": scored, "failed": failed, "ids": ids}

@router.post("/papers/{paper_id}/state")
async def set_state(paper_id: int, body: SetStateReq, session: AsyncSession = Depends(get_session)):
    if body.state not in [s.value for s in PaperState]:
        raise HTTPException(400, "invalid state")
    res = await session.execute(select(Paper).where(Paper.id == paper_id))
    paper = res.scalar_one_or_none()
    if not paper:
        raise HTTPException(404, "paper not found")
    paper.state = body.state
    session.add(paper)
    session.add(Action(paper_id=paper_id, action="set_state", payload={"state": body.state}, actor="nan"))
    await session.commit()
    return {"ok": True, "data": {"paper_id": paper_id, "state": body.state}}

@router.post("/papers/{paper_id}/tags")
async def tags(paper_id: int, body: TagsReq, session: AsyncSession = Depends(get_session)):
    res = await session.execute(select(Paper).where(Paper.id == paper_id))
    paper = res.scalar_one_or_none()
    if not paper:
        raise HTTPException(404, "paper not found")
    tags = set((paper.tags or {}).get("list", []))
    if body.add:
        tags.update(body.add)
    if body.remove:
        tags.difference_update(body.remove)
    paper.tags = {"list": sorted(tags)}
    session.add(paper)
    session.add(Action(paper_id=paper_id, action="tags", payload=paper.tags, actor="nan"))
    await session.commit()
    return {"ok": True, "data": {"paper_id": paper_id, "tags": paper.tags}}
