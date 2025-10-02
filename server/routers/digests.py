from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone, timedelta
from typing import Optional
from jinja2 import Environment, FileSystemLoader, select_autoescape
import os
from ..db import get_session
from ..models import Paper, PaperState
from ..services.ingest import parse_date_only
from .papers import _announced_date

router = APIRouter(tags=["digests"])

TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=select_autoescape(["html", "xml"])
)

def pick_top(papers, top_k=10):
    # Prefer must_read → further_read → triage (recent)
    must = [p for p in papers if p.state == PaperState.must_read.value or p.state == "shortlist"]
    futr = [p for p in papers if p.state == PaperState.further_read.value]
    tri = [p for p in papers if p.state == PaperState.triage.value]
    res = must[:top_k]
    if len(res) < top_k:
        res += futr[: (top_k - len(res))]
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
        # Default digest date in UTC+8 (configurable via DIGEST_TZ_OFFSET_HOURS)
        try:
            offset_hours = int(os.getenv("DIGEST_TZ_OFFSET_HOURS", "8"))
        except ValueError:
            offset_hours = 8
        local_today = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=offset_hours))).date()
        d = local_today
    d_str = d.isoformat()

    # Select papers whose announced date matches the requested date.
    # Uses the same ET-window policy as the papers API.
    stmt = select(Paper).order_by(Paper.id.desc())
    res = await session.execute(stmt)
    rows = res.scalars().all()
    day_rows = []
    for p in rows:
        ad = _announced_date(p.submitted_at)
        if ad == d_str:
            day_rows.append(p)
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
