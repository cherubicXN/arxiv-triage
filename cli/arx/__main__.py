import typer, webbrowser, os, json, requests, datetime as dt
from typing import Optional

app = typer.Typer(add_completion=False, help="arXiv News Agent CLI")
# app = typer.Typer()

API = os.environ.get("ARX_API", "http://localhost:8787")

@app.command("pull")
def pull(days: int = typer.Option(1, help="Window in days"),
         cats: Optional[str] = typer.Option("cs.CV", help="Comma-separated categories, e.g. cs.CV,cs.LG"),
         max_results: int = typer.Option(200, help="Max results to fetch")):
    
    url = f"{API}/v1/ingest/today"
    payload = {"days": days, "cats": cats.split(",") if cats else None, "max_results": max_results}
    r = requests.post(url, json=payload, timeout=120)
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
