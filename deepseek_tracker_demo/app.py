from __future__ import annotations

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .db import connect, init_db, list_events
from .poll import run_poll

app = FastAPI(title="DeepSeek Tracker Demo", version="0.1")

# Static assets
app.mount(
    "/static",
    StaticFiles(directory=str(__import__("pathlib").Path(__file__).parent / "static")),
    name="static",
)


@app.get("/api/health")
def health():
    s = get_settings()
    with connect(s.db_path) as conn:
        init_db(conn)
    return {"ok": True, "provider": s.provider}


@app.get("/api/events")
def api_events(
    provider: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
):
    s = get_settings()
    with connect(s.db_path) as conn:
        init_db(conn)
        return {"events": list_events(conn, provider=provider or s.provider, limit=limit)}


@app.post("/api/poll")
def api_poll():
    return run_poll()


@app.get("/", response_class=HTMLResponse)
def index():
    # Minimal inline HTML to keep the demo self-contained.
    return """<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>DeepSeek Tracker Demo</title>
  <link rel=\"stylesheet\" href=\"/static/style.css\" />
</head>
<body>
  <div class=\"wrap\">
    <header class=\"hdr\">
      <div>
        <h1>DeepSeek Tracker (demo)</h1>
        <p class=\"sub\">Poll GitHub releases + RSS, store to SQLite, render a feed.</p>
      </div>
      <div class=\"actions\">
        <button id=\"pollBtn\">Poll now</button>
        <a class=\"link\" href=\"/api/events\" target=\"_blank\" rel=\"noreferrer\">/api/events</a>
      </div>
    </header>

    <section class=\"meta\">
      <div id=\"status\" class=\"status\">Loading...</div>
      <div class=\"hint\">Configure sources via env: <code>DEEPSEEK_GITHUB_REPOS</code>, <code>DEEPSEEK_RSS_FEEDS</code>, <code>GITHUB_TOKEN</code>.</div>
    </section>

    <main>
      <div id=\"events\" class=\"events\"></div>
    </main>
  </div>

  <script src=\"/static/app.js\"></script>
</body>
</html>"""
