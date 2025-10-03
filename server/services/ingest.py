import httpx, asyncio, time, re
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone, timedelta
from ..models import Paper
from ..db import get_session
import yaml, os
from dateutil import parser as dtp
from loguru import logger

ARXIV_BASE = "https://export.arxiv.org/api/query"

def parse_date_only(s: str):
    return dtp.parse(s).date()

def _load_cfg_default():
    path = os.path.join(os.getcwd(), "config.yaml")
    if os.path.exists(path):
        with open(path, "r") as f:
            return yaml.safe_load(f)
    return {
        "sources": {"cats": ["cs.CV", "cs.LG"], "window_days": 1, "max_results": 200},
        "filters": {"include": [], "exclude": []},
        "output": {"digest_top_k": 10, "watchlist_k": 20},
    }

async def ensure_default_config():
    # noop in MLV; config is file-based unless updated via API
    return True

def _env_or_cfg_categories(cfg) -> List[str]:
    env_cats = os.getenv("ARXIV_CATEGORIES", "").strip()
    if env_cats:
        return [x.strip() for x in env_cats.split(",") if x.strip()]
    return cfg.get("sources", {}).get("cats", ["cs.CV", "cs.LG", "cs.RO"])

def _env_or_cfg_window_days(cfg) -> int:
    d = os.getenv("ARXIV_WINDOW_DAYS", "").strip()
    if d.isdigit():
        return int(d)
    return int(cfg.get("sources", {}).get("window_days", 1))

def _env_or_cfg_max_results(cfg) -> int:
    d = os.getenv("ARXIV_MAX_RESULTS", "").strip()
    if d.isdigit():
        return int(d)
    return int(cfg.get("sources", {}).get("max_results", 200))

async def fetch_arxiv(cats: List[str], days: int, max_results: int) -> List[Dict[str, Any]]:
    """
    Query arXiv Atom API for given categories within a recency window.
    """
    # Build query (use spaces so httpx encodes them as '+').
    # Parenthesize OR to be safe with precedence.
    cat_query = " OR ".join([f"cat:{c}" for c in cats])
    if len(cats) > 1:
        cat_query = f"({cat_query})"
    params = {
        "search_query": cat_query,
        # use lastUpdatedDate to capture revisions quickly
        # "sortBy": "lastUpdatedDate",
        "sortBy": "submittedDate",
        "sortOrder": "descending",
        "start": 0,
        "max_results": max_results
    }
    # etiquette: one request per ~3s
    # async with httpx.AsyncClient(timeout=30.0) as client:
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        logger.debug(f"arXiv request params: {params}")
        resp = await client.get(ARXIV_BASE, params=params, headers={"User-Agent": "arxiv-news-agent/0.1 (github.com/you)"})
        resp.raise_for_status()
        text = resp.text
    print(resp.url)

    # Manual parse: basic fields using regex (avoid adding feedparser at runtime)
    # (You can swap to feedparser if you prefer.)
    entries = text.split("<entry>")[1:]
    results = []
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)
    logger.debug(f"now_utc={now.isoformat()} cutoff_utc={cutoff.isoformat()} window_days={days}")
    kept, total = 0, 0
    sample_times = []
    for e in entries:
        def _get(tag):
            m = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", e, re.DOTALL)
            return (m.group(1).strip() if m else None)
        arxiv_id_full = _get("id") or ""
        # print(arxiv_id_full)
        # id example: http://arxiv.org/abs/2509.01234v2
        m = re.search(r"/abs/(\d{4}\.\d{4,5})(v(\d+))?", arxiv_id_full)
        if not m:
            continue
        arxiv_id = m.group(1)
        version = int(m.group(3) or "1")
        title = (_get("title") or "").replace("\n", " ").strip()
        abstract = (_get("summary") or "").replace("\n", " ").strip()
        published = _get("published")
        updated = _get("updated")
        try:
            pub_dt = dtp.parse(published) if published else None
            upd_dt = dtp.parse(updated) if updated else None
        except Exception:
            pub_dt = upd_dt = None

        def _to_utc(dt):
            if not dt:
                return None
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)

        pub_dt_utc = _to_utc(pub_dt)
        upd_dt_utc = _to_utc(upd_dt)

        # window filter: include if either published or updated within window
        total += 1
        if not ((pub_dt_utc and pub_dt_utc >= cutoff) or (upd_dt_utc and upd_dt_utc >= cutoff)):
            continue
        kept += 1
        if pub_dt_utc or upd_dt_utc:
            sample_times.append((pub_dt_utc.isoformat() if pub_dt_utc else None, upd_dt_utc.isoformat() if upd_dt_utc else None))

        # categories
        cats = re.findall(r'<category term="(.*?)"', e) or []
        primary_cat = cats[0] if cats else "unknown"

        # authors
        authors = ", ".join(re.findall(r"<name>(.*?)</name>", e))

        # links
        pdf_link = None
        html_abs = None
        for href, rel, _type in re.findall(r'<link href="(.*?)" rel="(.*?)"(?: type="(.*?)")?/?', e):
            if rel == "alternate":
                html_abs = href
            if rel == "related" and (_type or "").endswith("pdf"):
                pdf_link = href
        if not pdf_link:
            # common pattern
            pdf_link = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        if not html_abs:
            html_abs = f"https://arxiv.org/abs/{arxiv_id}"

        results.append({
            "arxiv_id": arxiv_id,
            "version": version,
            "title": title,
            "abstract": abstract,
            "authors": authors,
            "categories": ",".join(cats),
            "primary_category": primary_cat,
            "submitted_at": pub_dt_utc.isoformat() if pub_dt_utc else None,
            "updated_at": upd_dt_utc.isoformat() if upd_dt_utc else None,
            "links_pdf": pdf_link,
            "links_abs": html_abs,
            "links_html": f"https://ar5iv.org/html/{arxiv_id}",
            "extra": {}
        })
    logger.info(f"Fetched {len(results)} entries from arXiv (total_seen={total}, kept_after_window={kept})")
    if sample_times:
        head = sample_times[:5]
        logger.debug(f"sample published/updated (utc): {head}")
    return results

async def fetch_arxiv_by_ids(ids: List[str]) -> List[Dict[str, Any]]:
    if not ids:
        return []
    params = {
        "id_list": ",".join(ids)
    }
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        logger.debug(f"arXiv request by id params: {params}")
        resp = await client.get(ARXIV_BASE, params=params, headers={"User-Agent": "arxiv-news-agent/0.1 (github.com/you)"})
        resp.raise_for_status()
        text = resp.text
    entries = text.split("<entry>")[1:]
    out: List[Dict[str, Any]] = []
    for e in entries:
        def _get(tag):
            m = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", e, re.DOTALL)
            return (m.group(1).strip() if m else None)
        arxiv_id_full = _get("id") or ""
        m = re.search(r"/abs/(\d{4}\.\d{4,5})(v(\d+))?", arxiv_id_full)
        if not m:
            continue
        arxiv_id = m.group(1)
        version = int(m.group(3) or "1")
        title = (_get("title") or "").replace("\n", " ").strip()
        abstract = (_get("summary") or "").replace("\n", " ").strip()
        published = _get("published")
        updated = _get("updated")
        try:
            pub_dt = dtp.parse(published) if published else None
            upd_dt = dtp.parse(updated) if updated else None
        except Exception:
            pub_dt = upd_dt = None
        def _to_utc(dt):
            if not dt:
                return None
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        pub_dt_utc = _to_utc(pub_dt)
        upd_dt_utc = _to_utc(upd_dt)
        cats = re.findall(r'<category term="(.*?)"', e) or []
        primary_cat = cats[0] if cats else "unknown"
        authors = ", ".join(re.findall(r"<name>(.*?)</name>", e))
        pdf_link = None
        html_abs = None
        for href, rel, _type in re.findall(r'<link href="(.*?)" rel="(.*?)"(?: type="(.*?)")?/?', e):
            if rel == "alternate":
                html_abs = href
            if rel == "related" and (_type or "").endswith("pdf"):
                pdf_link = href
        if not pdf_link:
            pdf_link = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        if not html_abs:
            html_abs = f"https://arxiv.org/abs/{arxiv_id}"
        out.append({
            "arxiv_id": arxiv_id,
            "version": version,
            "title": title,
            "abstract": abstract,
            "authors": authors,
            "categories": ",".join(cats),
            "primary_category": primary_cat,
            "submitted_at": pub_dt_utc.isoformat() if pub_dt_utc else None,
            "updated_at": upd_dt_utc.isoformat() if upd_dt_utc else None,
            "links_pdf": pdf_link,
            "links_abs": html_abs,
            "links_html": f"https://ar5iv.org/html/{arxiv_id}",
            "extra": {}
        })
    logger.info(f"Fetched {len(out)} entries by id from arXiv")
    return out

async def ingest_by_id(session: AsyncSession, arxiv_id: str) -> int:
    papers = await fetch_arxiv_by_ids([arxiv_id])
    await upsert_papers(session, papers)
    return len(papers)

async def upsert_papers(session: AsyncSession, papers: List[Dict[str, Any]]):
    from ..models import Paper
    # naive upsert by (arxiv_id, version) → keep latest
    for p in papers:
        res = await session.execute(
            select(Paper).where(Paper.arxiv_id == p["arxiv_id"], Paper.version == p["version"])
        )
        row = res.scalar_one_or_none()
        if row:
            # update
            for k, v in p.items():
                setattr(row, k, v)
            session.add(row)
        else:
            row = Paper(**p)
            session.add(row)
    await session.commit()

async def ingest_today(session: AsyncSession, cats: List[str], days: int, max_results: int) -> int:
    papers = await fetch_arxiv(cats, days, max_results)
    await upsert_papers(session, papers)
    return len(papers)
