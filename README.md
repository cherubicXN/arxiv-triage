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
# or specify multiple categories:
python -m cli.arx pull -c cs.CV -c cs.LG --days 1
# Or via API:
curl -X POST http://localhost:8787/v1/ingest/today

# Batch-score papers (LLM rubric)
python -m cli.arx score-batch --state triage --provider deepseek --limit 15 --delay_ms 900

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
- Optional LLM rubric scoring:
  - OpenAI: set `OPENAI_API_KEY` (and optionally `OPENAI_BASE_URL`, `LLM_MODEL=gpt-4o-mini`).
  - DeepSeek: set `DEEPSEEK_API_KEY` and optionally `DEEPSEEK_BASE_URL=https://api.deepseek.com/v1`, `DEEPSEEK_MODEL=deepseek-chat`. You can also set `LLM_PROVIDER=deepseek` to make it the default.
  - Trigger scoring: `curl -X POST http://localhost:8787/v1/papers/123/score` (add `?provider=deepseek` to override per-call).
  - Falls back to a deterministic heuristic if keys or SDK are absent.
  - Calibration: control output strictness via `LLM_RUBRIC_SHRINK` (default 0.6) and `LLM_RUBRIC_BASELINE` (default 3). Scores are shrunk toward the baseline to avoid inflation.

#### Batch scoring
- Endpoint: `POST /v1/papers/score-batch`
- Body (JSON): `{ "state": "triage", "provider": "deepseek|openai", "limit": 20, "only_missing": true, "query": "optional bm25 query", "delay_ms": 800 }`
- Example:
```bash
curl -X POST http://localhost:8787/v1/papers/score-batch \
  -H 'Content-Type: application/json' \
  -d '{"state":"triage","provider":"deepseek","limit":15,"only_missing":true,"delay_ms":900}'
```

#### Batch tag suggestions
- Endpoint: `POST /v1/papers/suggest-tags-batch`
- Body (JSON): `{ "state": "triage", "provider": "deepseek|openai", "limit": 20, "only_missing": true, "query": "optional bm25 query", "delay_ms": 800 }`
- Example:
```bash
curl -X POST http://localhost:8787/v1/papers/suggest-tags-batch \
  -H 'Content-Type: application/json' \
  -d '{"state":"triage","provider":"deepseek","limit":20,"only_missing":true,"delay_ms":800}'
```

#### Tag suggestions
- Suggest tags for one paper and persist to signals:
```bash
curl -X POST 'http://localhost:8787/v1/papers/123/suggest-tags?provider=deepseek'
```
UI shows suggested tags below user tags; click to add.
- This is a starter you can expand into the full hub-and-spoke architecture later.
