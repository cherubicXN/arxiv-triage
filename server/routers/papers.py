from fastapi import APIRouter, Depends, Query, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from typing import List, Optional
from ..db import get_session
from ..models import Paper, Action, PaperState
from ..schemas import PapersResponse, PaperOut, SetStateReq, TagsReq
from ..services.scoring import search_bm25

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
    stmt = stmt.order_by(Paper.id.desc())
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
