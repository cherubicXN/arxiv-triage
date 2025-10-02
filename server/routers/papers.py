from fastapi import APIRouter, Depends, Query, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from typing import List, Optional
from fastapi.responses import StreamingResponse
import httpx
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
    BatchSuggestReq,
    BatchSuggestResp,
)
from ..services.scoring import search_bm25
from ..services.llm import llm_rubric_score, llm_suggest_tags
from dateutil import tz, parser as dtp

ET = tz.gettz("America/New_York")

def _announced_date(submitted_iso: Optional[str]) -> Optional[str]:
    if not submitted_iso:
        return None
    try:
        dt = dtp.parse(submitted_iso)
        if not dt.tzinfo:
            from datetime import timezone
            dt = dt.replace(tzinfo=timezone.utc)
        from datetime import timedelta, time
        dt_et = dt.astimezone(ET)
        wd = dt_et.weekday()  # Mon=0..Sun=6
        cutoff = time(14, 0)

        def next_weekday(base, target_wd):
            delta = (target_wd - base.weekday()) % 7
            return (base + timedelta(days=delta)).date()

        t = dt_et.timetz()

        if wd == 0:  # Monday
            return (dt_et.date() if t < cutoff else (dt_et + timedelta(days=1)).date()).isoformat()
        if wd == 1:  # Tuesday
            return (dt_et.date() if t < cutoff else (dt_et + timedelta(days=1)).date()).isoformat()
        if wd == 2:  # Wednesday
            return (dt_et.date() if t < cutoff else (dt_et + timedelta(days=1)).date()).isoformat()
        if wd == 3:  # Thursday
            if t < cutoff:
                return dt_et.date().isoformat()
            # Thu >=14:00 → announce Sunday (20:00)
            return next_weekday(dt_et, 6).isoformat()  # Sunday
        if wd == 4:  # Friday
            if t < cutoff:
                # Fri <14:00 belongs to Thu→Fri window → Sunday announce
                return next_weekday(dt_et, 6).isoformat()
            # Fri >=14:00 → Monday announce
            return next_weekday(dt_et, 0).isoformat()
        if wd == 5:  # Saturday → Monday announce
            return next_weekday(dt_et, 0).isoformat()
        if wd == 6:  # Sunday → Monday announce
            return next_weekday(dt_et, 0).isoformat()
        return None
    except Exception:
        return None

router = APIRouter(tags=["papers"])

async def _get_paper_by_arxiv(session: AsyncSession, arxiv_id: str, version: Optional[int] = None) -> Optional[Paper]:
    q = select(Paper).where(Paper.arxiv_id == arxiv_id)
    if version is not None:
        q = q.where(Paper.version == version)
    else:
        q = q.order_by(Paper.version.desc())
    res = await session.execute(q)
    if version is not None:
        return res.scalar_one_or_none()
    return res.scalars().first()

@router.get("/papers", response_model=PapersResponse)
async def list_papers(
    state: Optional[str] = Query(None),
    query: Optional[str] = Query(None),
    has_note: Optional[bool] = Query(None, description="Filter papers that have a non-empty note in extra.note"),
    category: Optional[str] = Query(None, description="Filter by primary_category (exact)"),
    tag: Optional[str] = Query(None, description="Filter by tag in tags.list; 'empty' for no tags"),
    announced_date: Optional[str] = Query(None, description="YYYY-MM-DD; derived from submitted_at per arXiv schedule (ET)"),
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

    if has_note is not None:
        def _has_note(p: Paper) -> bool:
            try:
                note = (p.extra or {}).get("note", "")
                return bool(str(note).strip())
            except Exception:
                return False
        rows = [p for p in rows if _has_note(p) == has_note]

    if category:
        rows = [p for p in rows if (p.primary_category or "") == category]

    if tag:
        if tag == "empty":
            rows = [p for p in rows if not ((p.tags or {}).get("list") or [])]
        else:
            rows = [p for p in rows if tag in ((p.tags or {}).get("list") or [])]

    if announced_date:
        rows = [p for p in rows if _announced_date(p.submitted_at) == announced_date]

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
    out = []
    for r in rows:
        item = PaperOut.model_validate(r).model_dump()
        item["announced_date"] = _announced_date(r.submitted_at)
        out.append(item)
    return {"ok": True, "data": out, "total": total}

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

@router.post("/papers/by_arxiv/{arxiv_id}/score")
async def score_paper_by_arxiv(
    arxiv_id: str,
    version: Optional[int] = Query(None),
    provider: str | None = Query(None, description="LLM provider: openai|deepseek"),
    session: AsyncSession = Depends(get_session),
):
    paper = await _get_paper_by_arxiv(session, arxiv_id, version)
    if not paper:
        raise HTTPException(404, "paper not found")
    scores = llm_rubric_score(paper.title or "", paper.abstract or "", provider=provider)
    sig = dict(paper.signals or {})
    sig["rubric"] = scores
    paper.signals = sig
    session.add(paper)
    await session.commit()
    return {"ok": True, "data": {"arxiv_id": arxiv_id, "version": paper.version, "rubric": scores}}

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

@router.post("/papers/by_arxiv/{arxiv_id}/suggest-tags")
async def suggest_tags_by_arxiv(
    arxiv_id: str,
    version: Optional[int] = Query(None),
    provider: str | None = Query(None, description="LLM provider: openai|deepseek"),
    session: AsyncSession = Depends(get_session),
):
    paper = await _get_paper_by_arxiv(session, arxiv_id, version)
    if not paper:
        raise HTTPException(404, "paper not found")
    suggestions = llm_suggest_tags(paper.title or "", paper.abstract or "", paper.categories or "", provider)
    sig = dict(paper.signals or {})
    sig["suggested_tags"] = suggestions
    paper.signals = sig
    session.add(paper)
    await session.commit()
    return {"ok": True, "data": {"arxiv_id": arxiv_id, "version": paper.version, "suggested": suggestions}}

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

@router.post("/papers/by_arxiv/{arxiv_id}/rubric", response_model=dict)
async def set_rubric_by_arxiv(
    arxiv_id: str,
    version: Optional[int] = Query(None),
    body: RubricSetReq = Body(...),
    session: AsyncSession = Depends(get_session),
):
    paper = await _get_paper_by_arxiv(session, arxiv_id, version)
    if not paper:
        raise HTTPException(404, "paper not found")
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
    return {"ok": True, "data": {"arxiv_id": arxiv_id, "version": paper.version, "rubric": scores}}

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
        # filter to year-month prefix, using announced date derived from submitted_at
        for p in rows:
            ad = _announced_date(p.submitted_at)
            if ad and ad.startswith(month):
                counts[ad] = counts.get(ad, 0) + 1
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
            ad = _announced_date(p.submitted_at)
            d = _to_date(ad)
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

@router.post("/papers/suggest-tags-batch", response_model=BatchSuggestResp)
async def suggest_tags_batch(body: BatchSuggestReq = Body(...), session: AsyncSession = Depends(get_session)):
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

    # Filter missing suggestions if requested
    if body.only_missing:
        rows = [p for p in rows if not ((p.signals or {}).get("suggested_tags"))]

    # Limit
    rows = rows[: max(0, int(body.limit))]

    suggested, failed, ids = 0, 0, []
    delay = max(0, int(body.delay_ms)) / 1000.0

    for p in rows:
        try:
            tags = await asyncio.to_thread(llm_suggest_tags, p.title or "", p.abstract or "", p.categories or "", body.provider)
            sig = dict(p.signals or {})
            sig["suggested_tags"] = tags
            p.signals = sig
            session.add(p)
            await session.commit()
            suggested += 1
            ids.append(p.id)
        except Exception:
            failed += 1
        if delay:
            await asyncio.sleep(delay)

    return {"ok": True, "suggested": suggested, "failed": failed, "ids": ids}

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

@router.post("/papers/by_arxiv/{arxiv_id}/state")
async def set_state_by_arxiv(arxiv_id: str, version: Optional[int] = Query(None), body: SetStateReq = Body(...), session: AsyncSession = Depends(get_session)):
    if body.state not in [s.value for s in PaperState]:
        raise HTTPException(400, "invalid state")
    paper = await _get_paper_by_arxiv(session, arxiv_id, version)
    if not paper:
        raise HTTPException(404, "paper not found")
    paper.state = body.state
    session.add(paper)
    session.add(Action(paper_id=paper.id, action="set_state", payload={"state": body.state}, actor="nan"))
    await session.commit()
    return {"ok": True, "data": {"arxiv_id": arxiv_id, "version": paper.version, "state": body.state}}

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

@router.post("/papers/by_arxiv/{arxiv_id}/tags")
async def tags_by_arxiv(arxiv_id: str, version: Optional[int] = Query(None), body: TagsReq = Body(...), session: AsyncSession = Depends(get_session)):
    paper = await _get_paper_by_arxiv(session, arxiv_id, version)
    if not paper:
        raise HTTPException(404, "paper not found")
    tags = set((paper.tags or {}).get("list", []))
    if body.add:
        tags.update(body.add)
    if body.remove:
        tags.difference_update(body.remove)
    paper.tags = {"list": sorted(tags)}
    session.add(paper)
    session.add(Action(paper_id=paper.id, action="tags", payload=paper.tags, actor="nan"))
    await session.commit()
    return {"ok": True, "data": {"arxiv_id": arxiv_id, "version": paper.version, "tags": paper.tags}}

@router.post("/papers/{paper_id}/note")
async def set_note(paper_id: int, body: dict = Body(...), session: AsyncSession = Depends(get_session)):
    res = await session.execute(select(Paper).where(Paper.id == paper_id))
    paper = res.scalar_one_or_none()
    if not paper:
        raise HTTPException(404, "paper not found")
    note_text = (body or {}).get("body", "")
    ext = dict(paper.extra or {})
    ext["note"] = note_text
    paper.extra = ext
    session.add(paper)
    session.add(Action(paper_id=paper.id, action="note", payload={"len": len(note_text)}, actor="nan"))
    await session.commit()
    return {"ok": True, "data": {"paper_id": paper_id, "note": note_text}}

@router.post("/papers/by_arxiv/{arxiv_id}/note")
async def set_note_by_arxiv(arxiv_id: str, version: Optional[int] = Query(None), body: dict = Body(...), session: AsyncSession = Depends(get_session)):
    paper = await _get_paper_by_arxiv(session, arxiv_id, version)
    if not paper:
        raise HTTPException(404, "paper not found")
    note_text = (body or {}).get("body", "")
    ext = dict(paper.extra or {})
    ext["note"] = note_text
    paper.extra = ext
    session.add(paper)
    session.add(Action(paper_id=paper.id, action="note", payload={"len": len(note_text)}, actor="nan"))
    await session.commit()
    return {"ok": True, "data": {"arxiv_id": arxiv_id, "version": paper.version, "note": note_text}}

@router.get("/papers/{paper_id}/pdf")
async def get_pdf(paper_id: int, session: AsyncSession = Depends(get_session)):
    res = await session.execute(select(Paper).where(Paper.id == paper_id))
    paper = res.scalar_one_or_none()
    if not paper:
        raise HTTPException(404, "paper not found")
    url = paper.links_pdf or (f"https://arxiv.org/pdf/{paper.arxiv_id}.pdf" if paper.arxiv_id else None)
    if not url:
        raise HTTPException(404, "pdf url not available")
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            upstream = await client.get(url)
            upstream.raise_for_status()
            headers = {"Content-Type": "application/pdf", "Cache-Control": "public, max-age=86400"}
            return StreamingResponse(iter([upstream.content]), media_type="application/pdf", headers=headers)
    except httpx.HTTPError as e:
        raise HTTPException(502, f"failed to fetch pdf: {e}")

@router.get("/papers/by_arxiv/{arxiv_id}/pdf")
async def get_pdf_by_arxiv(arxiv_id: str, version: Optional[int] = Query(None), session: AsyncSession = Depends(get_session)):
    paper = await _get_paper_by_arxiv(session, arxiv_id, version)
    if not paper:
        raise HTTPException(404, "paper not found")
    url = paper.links_pdf or f"https://arxiv.org/pdf/{paper.arxiv_id}.pdf"
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            upstream = await client.get(url)
            upstream.raise_for_status()
            headers = {"Content-Type": "application/pdf", "Cache-Control": "public, max-age=86400"}
            return StreamingResponse(iter([upstream.content]), media_type="application/pdf", headers=headers)
    except httpx.HTTPError as e:
        raise HTTPException(502, f"failed to fetch pdf: {e}")
