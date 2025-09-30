from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Integer, DateTime, Text, JSON, Enum
from sqlalchemy.sql import func
from typing import Optional
from datetime import datetime
import enum
from .db import Base

class PaperState(str, enum.Enum):
    triage = "triage"
    shortlist = "shortlist"
    archived = "archived"
    hidden = "hidden"

class Paper(Base):
    __tablename__ = "papers"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    arxiv_id: Mapped[str] = mapped_column(String(32), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    title: Mapped[str] = mapped_column(Text)
    authors: Mapped[str] = mapped_column(Text)  # comma-separated
    abstract: Mapped[str] = mapped_column(Text)
    categories: Mapped[str] = mapped_column(String(128))  # comma-separated
    primary_category: Mapped[str] = mapped_column(String(32))
    submitted_at: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    updated_at: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    links_pdf: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    links_html: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    links_abs: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    extra: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    tags: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # {list: []}
    signals: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # bm25, rubric, etc.
    state: Mapped[str] = mapped_column(String(16), default=PaperState.triage.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class Action(Base):
    __tablename__ = "actions"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    paper_id: Mapped[int] = mapped_column(Integer, index=True)
    action: Mapped[str] = mapped_column(String(32))
    payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    actor: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class ConfigKV(Base):
    __tablename__ = "config_kv"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
