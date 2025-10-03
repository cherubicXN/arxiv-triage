import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from .ingest import upsert_papers
from ..models import ConfigKV

ARXIV_OAI_BASE = "https://oaipmh.arxiv.org/oai"


def _utc_date_only(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).date().isoformat()


def _strip_ns(tag: str) -> str:
    return tag.split('}', 1)[-1] if '}' in tag else tag


def _xml_iter_children(elem):
    for c in list(elem):
        yield _strip_ns(c.tag), c


def _parse_oai_record(record_xml: str) -> Optional[Dict[str, Any]]:
    """Parse a single <record> XML chunk into our Paper dict.
    We avoid strict namespace reliance by stripping tag namespaces.
    """
    import xml.etree.ElementTree as ET

    try:
        root = ET.fromstring(record_xml)
    except Exception:
        return None

    header = root.find('.//*')  # first child under record
    # Resolve header node
    hdr = None
    for tag, node in _xml_iter_children(root):
        if tag == 'header':
            hdr = node
            break
    if hdr is None:
        return None

    # Skip deleted
    if hdr.attrib.get('status') == 'deleted':
        return None

    identifier = None
    datestamp = None
    for t, n in _xml_iter_children(hdr):
        if t == 'identifier':
            identifier = (n.text or '').strip()
        elif t == 'datestamp':
            datestamp = (n.text or '').strip()
    if not identifier:
        return None
    # identifier like oai:arXiv:2501.01234
    arxiv_id = identifier.split(':')[-1]

    # metadata block → arXiv specific structure
    md = None
    for tag, node in _xml_iter_children(root):
        if tag == 'metadata':
            md = node
            break
    if md is None:
        return None

    # arXiv element lives under metadata; find first child element
    arx = None
    for _, node in _xml_iter_children(md):
        arx = node
        break
    if arx is None:
        return None

    title = ''
    abstract = ''
    authors_list: List[str] = []
    categories_tokens: List[str] = []
    created_ts: Optional[str] = None
    versions: List[Tuple[int, str]] = []  # (vnum, date)

    for tag, node in _xml_iter_children(arx):
        if tag == 'title':
            title = (node.text or '').strip()
        elif tag == 'abstract':
            abstract = (node.text or '').strip()
        elif tag == 'authors':
            # authors/author with keyname + forenames
            for _t, a in _xml_iter_children(node):
                if _t != 'author':
                    continue
                keyname = ''
                forenames = ''
                fullname = ''
                for __t, f in _xml_iter_children(a):
                    if __t == 'keyname':
                        keyname = (f.text or '').strip()
                    elif __t == 'forenames':
                        forenames = (f.text or '').strip()
                    elif __t == 'name':
                        fullname = (f.text or '').strip()
                if fullname:
                    authors_list.append(fullname)
                else:
                    name = (forenames + ' ' + keyname).strip()
                    if name:
                        authors_list.append(name)
        elif tag == 'categories':
            text = (node.text or '').strip()
            if text:
                categories_tokens = [tok for tok in text.split() if tok]
        elif tag == 'created':
            created_ts = (node.text or '').strip()
        elif tag == 'versions':
            for __t, v in _xml_iter_children(node):
                if __t != 'version':
                    continue
                vlabel = v.attrib.get('version', '')  # like v2
                vnum = 0
                if vlabel.startswith('v'):
                    try:
                        vnum = int(vlabel[1:])
                    except Exception:
                        vnum = 0
                vdate = ''
                for ___t, f in _xml_iter_children(v):
                    if ___t == 'date':
                        vdate = (f.text or '').strip()
                versions.append((vnum, vdate))

    version = max([v for v, _ in versions], default=1)
    # submitted/updated timestamps: derive from versions if present
    submitted_at = None
    updated_at = None
    if versions:
        # earliest as submitted, latest as updated
        vsorted = sorted(versions, key=lambda x: x[0])
        submitted_at = vsorted[0][1] or created_ts
        updated_at = vsorted[-1][1] or datestamp
    else:
        submitted_at = created_ts
        updated_at = datestamp

    cats = categories_tokens
    primary_cat = cats[0] if cats else 'unknown'

    return {
        "arxiv_id": arxiv_id,
        "version": version,
        "title": title,
        "abstract": abstract,
        "authors": ", ".join(authors_list),
        "categories": ",".join(cats),
        "primary_category": primary_cat,
        "submitted_at": submitted_at,
        "updated_at": updated_at,
        "links_pdf": f"https://arxiv.org/pdf/{arxiv_id}.pdf",
        "links_abs": f"https://arxiv.org/abs/{arxiv_id}",
        "links_html": f"https://ar5iv.org/html/{arxiv_id}",
        "extra": {}
    }


async def _oai_list_records_once(client: httpx.AsyncClient, params: Dict[str, str]) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    logger.debug(f"OAI-PMH request params: {params}")
    r = await client.get(ARXIV_OAI_BASE, params=params, headers={"User-Agent": "arxiv-news-agent/0.1 (github.com/you)"})
    r.raise_for_status()
    text = r.text

    # Split by <record> to avoid dealing with heavier XML parsing for pagination
    recs_raw = text.split('<record>')[1:]
    out: List[Dict[str, Any]] = []
    for raw in recs_raw:
        # close tag included at end, rebuild element for parser
        raw_xml = '<record>' + raw
        rec = _parse_oai_record(raw_xml)
        if rec:
            out.append(rec)

    # Extract resumptionToken if present
    # Token may be empty content when finished
    import re
    m = re.search(r"<resumptionToken[^>]*>(.*?)</resumptionToken>", text, re.DOTALL)
    token = m.group(1).strip() if m else None
    if token == '':
        token = None
    return out, token


async def harvest_oai_category(cat: str, since_date_iso: str, until_date_iso: str, delay_seconds: float = 3.0) -> List[Dict[str, Any]]:
    """Harvest a single category using OAI-PMH ListRecords.
    since/until are date-only strings (YYYY-MM-DD) to match arXiv granularity.
    """
    cat_oai = cat.replace(".", ":")

    params: Dict[str, str] = {
        "verb": "ListRecords",
        "metadataPrefix": "arXiv",
        "set": f"cs:{cat_oai}",
        "from": since_date_iso,
        "until": until_date_iso,
    }
    all_rows: List[Dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=40.0, follow_redirects=True) as client:
        page = 0
        while True:
            page += 1
            rows, token = await _oai_list_records_once(client, params)
            all_rows.extend(rows)
            logger.info(f"OAI {cat}: fetched page {page}, rows+={len(rows)}, total={len(all_rows)}")
            if not token:
                break
            # Next page with resumptionToken
            params = {"verb": "ListRecords", "resumptionToken": token}
            if delay_seconds > 0:
                await asyncio.sleep(delay_seconds)
    return all_rows


async def get_oai_checkpoint(session: AsyncSession, cat: str) -> Optional[str]:
    key = f"oai_last_{cat}"
    res = await session.execute(select(ConfigKV).where(ConfigKV.key == key))
    row = res.scalar_one_or_none()
    if row and row.value and isinstance(row.value, dict):
        return row.value.get("datestamp")
    return None


async def set_oai_checkpoint(session: AsyncSession, cat: str, datestamp: str) -> None:
    key = f"oai_last_{cat}"
    res = await session.execute(select(ConfigKV).where(ConfigKV.key == key))
    row = res.scalar_one_or_none()
    val = {"datestamp": datestamp}
    if row:
        row.value = val
        session.add(row)
    else:
        row = ConfigKV(key=key, value=val)
        session.add(row)
    await session.commit()


async def ingest_oai(session: AsyncSession, cats: List[str], days: int = 3, use_checkpoint: bool = True) -> int:
    """Harvest papers via OAI-PMH for given categories and upsert.
    If use_checkpoint, start from the last stored datestamp per-cat; else from now-days.
    """
    now = datetime.now(timezone.utc)
    until = _utc_date_only(now)
    total_added = 0
    for cat in cats:
        since = None
        if use_checkpoint:
            since = await get_oai_checkpoint(session, cat)
        if not since:
            since = _utc_date_only(now - timedelta(days=days))

        logger.info(f"OAI harvest start: cat={cat} from={since} until={until}")
        rows = await harvest_oai_category(cat, since, until)
        
        if rows:
            await upsert_papers(session, rows)
            total_added += len(rows)
        await set_oai_checkpoint(session, cat, until)
    return total_added

