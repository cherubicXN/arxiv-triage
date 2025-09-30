from fastapi import FastAPI, Depends, Query, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import os
from .db import init_db, get_session, Settings
from .routers import papers, digests, config as cfg, ingest
from .services.ingest import ensure_default_config

app = FastAPI(title="arXiv News Agent", version="0.1.0")

# CORS (allow local web apps)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    await init_db()
    await ensure_default_config()

# Routers
app.include_router(papers.router, prefix="/v1")
app.include_router(ingest.router, prefix="/v1")
app.include_router(digests.router, prefix="/v1")
app.include_router(cfg.router, prefix="/v1")

@app.get("/")
async def root():
    return {"ok": True, "data": {"message": "arXiv News Agent API", "docs": "/docs"}}
