from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class PaperOut(BaseModel):
    id: int
    arxiv_id: str
    version: int
    title: str
    authors: str
    abstract: str
    categories: str
    primary_category: str
    submitted_at: Optional[str]
    updated_at: Optional[str]
    links_pdf: Optional[str]
    links_html: Optional[str]
    links_abs: Optional[str]
    extra: Optional[Dict[str, Any]]
    tags: Optional[Dict[str, Any]]
    signals: Optional[Dict[str, Any]]
    state: str
    class Config:
        from_attributes = True

class PapersResponse(BaseModel):
    ok: bool = True
    data: List[PaperOut]
    total: int

class SetStateReq(BaseModel):
    state: str

class NoteReq(BaseModel):
    body: str

class TagsReq(BaseModel):
    add: Optional[List[str]] = None
    remove: Optional[List[str]] = None

class IngestReq(BaseModel):
    days: int = 1
    cats: Optional[List[str]] = None
    max_results: Optional[int] = None
