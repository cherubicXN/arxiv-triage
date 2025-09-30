from fastapi import APIRouter, Depends, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Dict, Any
import yaml
import os
from ..db import get_session
from ..models import ConfigKV

router = APIRouter(tags=["config"])

DEFAULT_CONFIG_PATH = os.path.join(os.getcwd(), "config.yaml")

async def _load_config(session: AsyncSession):
    res = await session.execute(select(ConfigKV).where(ConfigKV.key == "config"))
    kv = res.scalar_one_or_none()
    if kv and kv.value:
        return kv.value
    # fallback to file
    if os.path.exists(DEFAULT_CONFIG_PATH):
        with open(DEFAULT_CONFIG_PATH, "r") as f:
            return yaml.safe_load(f)
    return {}

@router.get("/config")
async def get_config(session: AsyncSession = Depends(get_session)):
    cfg = await _load_config(session)
    return {"ok": True, "data": cfg}

@router.put("/config")
async def put_config(body: Dict[str, Any] = Body(...), session: AsyncSession = Depends(get_session)):
    res = await session.execute(select(ConfigKV).where(ConfigKV.key == "config"))
    kv = res.scalar_one_or_none()
    if not kv:
        kv = ConfigKV(key="config", value=body)
    else:
        # merge shallowly
        merged = dict(kv.value or {})
        merged.update(body)
        kv.value = merged
    session.add(kv)
    await session.commit()
    return {"ok": True, "data": kv.value}
