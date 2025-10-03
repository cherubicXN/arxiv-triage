import typer, webbrowser, os, json, requests, datetime as dt
from typing import Optional

app = typer.Typer(add_completion=False, help="arXiv News Agent CLI")
# app = typer.Typer()

API = os.environ.get("ARX_API", "http://localhost:8787")

@app.command("pull")
def pull(
    days: int = typer.Option(1, help="Window in days"),
    cat: Optional[list[str]] = typer.Option(None, "--cat", "-c", help="Repeatable category option, e.g. -c cs.CV -c cs.LG"),
    cats: Optional[str] = typer.Option(None, help="Comma-separated categories (alternative to --cat)"),
    max_results: int = typer.Option(200, help="Max results to fetch"),
    oai: bool = typer.Option(False, help="Use OAI-PMH incremental harvester"),
):
    """
    Ingest today's papers for one or more categories.
    Category selection precedence:
      1) Repeated --cat/-c options
      2) --cats comma-separated string
      3) None → let server use config/env defaults
    """
    url = f"{API}/v1/ingest/oai" if oai else f"{API}/v1/ingest/today"
    cats_list = None
    if cat and len(cat) > 0:
        cats_list = [c.strip() for c in cat if c and c.strip()]
    elif cats:
        cats_list = [x.strip() for x in cats.split(",") if x.strip()]
    if oai:
        payload = {"days": days, "cats": cats_list, "use_checkpoint": True}
    else:
        payload = {"days": days, "cats": cats_list, "max_results": max_results}
    r = requests.post(url, json=payload, timeout=120)
    typer.echo(r.json())

@app.command("score-batch")
def score_batch(
    state: Optional[str] = typer.Option(None, help="Filter by state: triage|shortlist|archived|hidden"),
    provider: Optional[str] = typer.Option(None, help="LLM provider: openai|deepseek (overrides env)"),
    limit: int = typer.Option(20, min=1, help="Max papers to score"),
    only_missing: bool = typer.Option(True, help="Only score papers missing rubric"),
    query: Optional[str] = typer.Option(None, help="Optional BM25 query to narrow set"),
    delay_ms: int = typer.Option(800, min=0, help="Delay between calls (ms) to avoid rate spikes"),
):
    """Batch score papers with LLM rubric and persist results."""
    url = f"{API}/v1/papers/score-batch"
    payload = {
        "state": state,
        "provider": provider,
        "limit": limit,
        "only_missing": only_missing,
        "query": query,
        "delay_ms": delay_ms,
    }
    r = requests.post(url, json=payload, timeout=600)
    typer.echo(r.json())

@app.command("suggest-batch")
def suggest_batch(
    state: Optional[str] = typer.Option(None, help="Filter by state: triage|shortlist|archived|hidden"),
    provider: Optional[str] = typer.Option(None, help="LLM provider: openai|deepseek (overrides env)"),
    limit: int = typer.Option(20, min=1, help="Max papers to suggest for"),
    only_missing: bool = typer.Option(True, help="Only papers missing suggested tags"),
    query: Optional[str] = typer.Option(None, help="Optional BM25 query to narrow set"),
    delay_ms: int = typer.Option(800, min=0, help="Delay between calls (ms) to avoid rate spikes"),
):
    """Batch suggest tags with LLM and persist to signals.suggested_tags."""
    url = f"{API}/v1/papers/suggest-tags-batch"
    payload = {
        "state": state,
        "provider": provider,
        "limit": limit,
        "only_missing": only_missing,
        "query": query,
        "delay_ms": delay_ms,
    }
    r = requests.post(url, json=payload, timeout=600)
    typer.echo(r.json())

@app.command("list")
def list_cmd(state: Optional[str] = typer.Option(None, help="triage|shortlist|archived|hidden"),
             top: int = typer.Option(50, help="max to show"),
             query: Optional[str] = typer.Option(None, help='e.g. "line OR plane"')):
    url = f"{API}/v1/papers"
    params = {"state": state, "page": 1, "page_size": top}
    if query: params["query"] = query
    r = requests.get(url, params=params, timeout=60)
    data = r.json()
    for p in data.get("data", []):
        typer.echo(f"[{p['id']}] {p['title']}  —  {p['authors']}  [{p['primary_category']}]")
    typer.echo(f"Total: {data.get('total', 0)}")

@app.command("keep")
def keep(paper_id: int):
    url = f"{API}/v1/papers/{paper_id}/state"
    r = requests.post(url, json={"state": "shortlist"}, timeout=30)
    typer.echo(r.json())

@app.command("meh")
def meh(paper_id: int):
    url = f"{API}/v1/papers/{paper_id}/state"
    r = requests.post(url, json={"state": "archived"}, timeout=30)
    typer.echo(r.json())

@app.command("tag")
def tag(paper_id: int, tags: str):
    url = f"{API}/v1/papers/{paper_id}/tags"
    add = [t.strip() for t in tags.split(",") if t.strip()]
    r = requests.post(url, json={"add": add}, timeout=30)
    typer.echo(r.json())

@app.command("digest")
def digest(date: Optional[str] = typer.Option(None, help="YYYY-MM-DD (default: today)"),
           open_html: bool = typer.Option(True, "--open/--no-open", help="Open HTML in browser"),
           top_k: int = typer.Option(10)):
    if not date:
        date = dt.date.today().isoformat()
    url = f"{API}/v1/digests/daily"
    r = requests.get(url, params={"date": date, "format": "html", "top_k": top_k}, timeout=60)
    data = r.json()

    if "data" in data:
        # Write to temp file
        path = f"/tmp/arx_digest_{date}.html"
        with open(path, "w") as f:
            f.write(data["data"])
        if open_html:
            webbrowser.open(f"file://{path}")
        typer.echo(f"Wrote {path}")
    else:
        typer.echo(data)

if __name__ == "__main__":
    app()
