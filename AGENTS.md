# Repository Guidelines

## Project Structure & Module Organization
- `server/`: FastAPI app. Entry `server/main.py`; API in `server/routers/*`; data models/schemas in `server/models.py`, `server/schemas.py`; business logic in `server/services/*`; DB setup in `server/db.py`; templates at `server/templates/`.
- `cli/arx/`: Python CLI (`python -m cli.arx …`) for ingest, triage, and digest.
- `src/`: Minimal React/Vite UI. Alternate UI in `arxiv-triage-ui/` (same commands).
- Config: `config.yaml`, `.env` (copy from `.env.example`). Docker/Postgres: `docker-compose.yml`.

## Build, Test, and Development Commands
- Python env: `python3.10 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
- Run API: `uvicorn server.main:app --reload --port 8787`
- Ingest today: `python -m cli.arx pull --days 1`
- Triage/Digest: `python -m cli.arx list --state triage --top 30`; `python -m cli.arx digest --open`
- Frontend (root or `arxiv-triage-ui/`): `npm install && npm run dev`
- Postgres (optional): `docker compose up -d`; then set `DATABASE_URL=postgresql+psycopg2://arx:arx@localhost:5432/arx`

## Coding Style & Naming Conventions
- Python: PEP 8, 4 spaces, type hints. `snake_case` for functions/vars; `PascalCase` for classes. Keep I/O in `routers/`, core logic in `services/`.
- TS/React: 2 spaces; `PascalCase` components, `camelCase` props; reusable UI in `src/components/`.
- Keep lines ≤ 100 chars; prefer pure functions and small modules. No enforced linters—match current style.

## Testing Guidelines
- No formal suite yet. Use `pytest`; place tests in `tests/` or `server/tests/` as `test_*.py`.
- For API tests, use `httpx` client against `server.main:app` and seed minimal fixtures.
- Aim to cover routers and services with focused, fast tests.

## Commit & Pull Request Guidelines
- Commits: imperative mood, scoped prefixes when helpful (e.g., `server:`, `cli:`, `ui:`), concise subject, focused diffs. Conventional Commits welcome (`feat:`, `fix:`).
- PRs: clear description, linked issues, reproduction/validation steps, UI screenshots when relevant, and notes on config/env changes.

## Security & Configuration Tips
- Never commit secrets. Use `.env`; reference `.env.example` for keys like `OPENAI_API_KEY`.
- Default DB is SQLite at `./arx.db`. Respect arXiv etiquette (throttle; avoid unnecessary fetch loops).
