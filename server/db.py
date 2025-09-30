import os
import asyncio
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()

Base = declarative_base()

def _default_db_url() -> str:
    db_url_env = os.getenv("DATABASE_URL", "").strip()
    if db_url_env:
        # If non-async driver is given (e.g., psycopg2), that's fine for sync engines,
        # but we use async engine. Convert common URLs to async variants.
        if db_url_env.startswith("sqlite:///"):
            return "sqlite+aiosqlite:///" + db_url_env[len("sqlite:///"):]
        if db_url_env.startswith("postgresql+psycopg2"):
            return db_url_env.replace("postgresql+psycopg2", "postgresql+asyncpg")
        if db_url_env.startswith("postgresql://"):
            return db_url_env.replace("postgresql://", "postgresql+asyncpg://")
        return db_url_env
    # default sqlite
    return "sqlite+aiosqlite:///./arx.db"

ASYNC_DATABASE_URL = _default_db_url()

engine = create_async_engine(ASYNC_DATABASE_URL, echo=False, future=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, autoflush=False, autocommit=False, class_=AsyncSession)

async def init_db():
    async with engine.begin() as conn:
        from .models import Paper, Action, ConfigKV
        await conn.run_sync(Base.metadata.create_all)

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session

class Settings:
    port: int = int(os.getenv("PORT", "8787"))
