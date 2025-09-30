from fastapi import APIRouter, Depends, Body
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from ..db import get_session
from ..schemas import IngestReq
from ..services.ingest import ingest_today, _load_cfg_default, _env_or_cfg_categories, _env_or_cfg_window_days, _env_or_cfg_max_results

router = APIRouter(tags=["ingest"])

@router.post("/ingest/today")
async def ingest_today_ep(payload: IngestReq = Body(...), session: AsyncSession = Depends(get_session)):
    cfg = _load_cfg_default()
    cats = payload.cats or _env_or_cfg_categories(cfg)
    days = payload.days or _env_or_cfg_window_days(cfg)
    max_results = payload.max_results or _env_or_cfg_max_results(cfg)
    count = await ingest_today(session, cats=cats, days=days, max_results=max_results)
    return {"ok": True, "data": {"fetched": count, "cats": cats, "days": days}}
