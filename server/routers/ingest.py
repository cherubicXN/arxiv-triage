from fastapi import APIRouter, Depends, Body, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from ..db import get_session
from ..schemas import IngestReq, IngestByIdReq, IngestOAIReq
from ..services.ingest import ingest_today, ingest_by_id, _load_cfg_default, _env_or_cfg_categories, _env_or_cfg_window_days, _env_or_cfg_max_results
from ..services.oai import ingest_oai

router = APIRouter(tags=["ingest"])

@router.post("/ingest/today")
async def ingest_today_ep(payload: IngestReq = Body(...), session: AsyncSession = Depends(get_session)):
    cfg = _load_cfg_default()
    cats = payload.cats or _env_or_cfg_categories(cfg)
    days = payload.days or _env_or_cfg_window_days(cfg)
    max_results = payload.max_results or _env_or_cfg_max_results(cfg)
    try:
        count = await ingest_today(session, cats=cats, days=days, max_results=max_results)
    except Exception as e:
        # Surface a readable error instead of generic 500s (e.g., network blocked)
        raise HTTPException(status_code=502, detail=f"ingest failed: {e}")
    return {"ok": True, "data": {"fetched": count, "cats": cats, "days": days, "max_results": max_results}}

@router.post("/ingest/by_id")
async def ingest_by_id_ep(payload: IngestByIdReq = Body(...), session: AsyncSession = Depends(get_session)):
    try:
        count = await ingest_by_id(session, payload.arxiv_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"ingest by id failed: {e}")
    return {"ok": True, "data": {"fetched": count, "arxiv_id": payload.arxiv_id}}

@router.post("/ingest/oai")
async def ingest_oai_ep(payload: IngestOAIReq = Body(...), session: AsyncSession = Depends(get_session)):
    cfg = _load_cfg_default()
    cats = payload.cats or _env_or_cfg_categories(cfg)
    days = payload.days or _env_or_cfg_window_days(cfg)
    try:
        count = await ingest_oai(session, cats=cats, days=days, use_checkpoint=payload.use_checkpoint)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"oai ingest failed: {e}")
    return {"ok": True, "data": {"fetched": count, "cats": cats, "days": days, "use_checkpoint": payload.use_checkpoint}}
