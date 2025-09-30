# arxiv-news-agent (MLV — Minimum Lovable Version)

A modular agent to ingest new papers from arXiv, triage them with rules + BM25 (+ optional LLM rubric scoring), and produce a daily digest.  
Default DB is SQLite for zero-friction; switch to Postgres by setting `DATABASE_URL`.

## Features (in this repo)
- FastAPI backend with REST endpoints:
  - `POST /v1/ingest/today` — fetch + normalize + score (configurable categories & window).
  - `GET /v1/papers` — list/query papers with filters & pagination.
  - `POST /v1/papers/{id}/state` — set state: `triage|shortlist|archived|hidden`.
  - `GET /v1/digests/daily?date=YYYY-MM-DD&format=markdown|html|json` — daily digest.
  - `GET /v1/config` & `PUT /v1/config` — edit knobs (sources, filters, quotas, scorer weights).
- YAML config, persisted overrides in DB.
- Scoring: simple BM25 over title+abstract; optional LLM rubric (GPT-5 Pro) if key provided.
- CLI (`arx`) for muscle-memory triage: list/keep/meh/tag/note/digest.
- Basic HTML digest page via Jinja2 (server-rendered, no JS build step required).

## Quickstart
```bash
# 1) Python env
python3.10 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2) Configure (optional)
cp .env.example .env
# edit .env to set categories, OPENAI_API_KEY, or DATABASE_URL (leave empty for SQLite)

# 3) Run API
uvicorn server.main:app --reload --port 8787

# 4) Ingest today's papers (default cats from .env or config.yaml)
python -m cli.arx pull --days 1
# Or via API:
curl -X POST http://localhost:8787/v1/ingest/today

# 5) Open digest (HTML) for today
python -m cli.arx digest --open

# 6) Triage from CLI
python -m cli.arx list --state triage --top 30 --query "line OR plane"
python -m cli.arx keep <paper_id>
python -m cli.arx meh <paper_id>
```

### Optional: Postgres via Docker
```bash
docker compose up -d
# Then run API with DATABASE_URL pointing to Postgres
DATABASE_URL=postgresql+psycopg2://arx:arx@localhost:5432/arx uvicorn server.main:app --port 8787
```

### Notes
- arXiv etiquette: throttle requests (we use 1 req/3s) and cache ETags. 
- If `OPENAI_API_KEY` is set, the scorer will call model `gpt-5-pro` for a rubric score.
- This is a starter you can expand into the full hub-and-spoke architecture later.
