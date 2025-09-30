from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone
from typing import Optional
from jinja2 import Environment, FileSystemLoader, select_autoescape
import os
from ..db import get_session
from ..models import Paper, PaperState
from ..services.ingest import parse_date_only

router = APIRouter(tags=["digests"])

TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=select_autoescape(["html", "xml"])
)

def pick_top(papers, top_k=10):
    # simple heuristic: prefer shortlist → triage by id (recent)
    short = [p for p in papers if p.state == PaperState.shortlist.value]
    tri = [p for p in papers if p.state == PaperState.triage.value]
    res = short[:top_k]
    if len(res) < top_k:
        res += tri[: (top_k - len(res))]
    return res

@router.get("/digests/daily")
async def digest_daily(
    date: Optional[str] = Query(None, description="YYYY-MM-DD (default: today UTC)"),
    format: str = Query("markdown", pattern="^(markdown|html|json)$"),
    top_k: int = Query(10, ge=1, le=100),
    session: AsyncSession = Depends(get_session)
):
    if date:
        d = parse_date_only(date)
    else:
        d = datetime.now(timezone.utc).date()
    d_str = d.isoformat()

    # select papers submitted/updated on that date (approx: string prefix match)
    stmt = select(Paper).order_by(Paper.id.desc())
    res = await session.execute(stmt)
    rows = res.scalars().all()
    day_rows = [p for p in rows if (p.submitted_at and p.submitted_at.startswith(d_str)) or (p.updated_at and p.updated_at.startswith(d_str))]
    top = pick_top(day_rows, top_k=top_k)

    if format == "json":
        return {"ok": True, "data": [{"id": p.id, "title": p.title, "arxiv": p.arxiv_id, "state": p.state} for p in top], "count": len(top), "date": d_str}
    if format == "markdown":
        md = f"# arXiv Daily Digest — {d_str}\n\n"
        for i, p in enumerate(top, 1):
            md += f"{i}. **{p.title}**  \n   {p.authors}  \n   `[{p.primary_category}]` — [abs]({p.links_abs}) · [pdf]({p.links_pdf})\n\n"
        return {"ok": True, "data": md, "count": len(top), "date": d_str}
    # html
    tmpl = env.get_template("digest.html")
    html = tmpl.render(date=d_str, papers=top)
    return {"ok": True, "data": html, "count": len(top), "date": d_str}
