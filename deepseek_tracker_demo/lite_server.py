from __future__ import annotations

import argparse
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from .config import get_settings
from .db import connect, init_db, list_events
from .lite_poll import poll_homepage_once


_HTML = """<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>DeepSeekV4 Spotter</title>
  <style>
    :root {
      --bg0: #04090e;
      --bg1: #0d1620;
      --ink: #e9f8ff;
      --muted: rgba(233,248,255,0.72);
      --line: rgba(168, 209, 234, 0.25);
      --panel: rgba(12, 28, 39, 0.75);
      --ok: #66f3a6;
      --warn: #ffd166;
      --err: #ff7c8b;
      --accent: #7cf6ff;
      --mono: "IBM Plex Mono", "JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
      --sans: "Space Grotesk", "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      color: var(--ink);
      font-family: var(--sans);
      background:
        radial-gradient(1100px 700px at 0% -10%, rgba(124,246,255,0.15), transparent 55%),
        radial-gradient(900px 500px at 110% -20%, rgba(102,243,166,0.18), transparent 55%),
        linear-gradient(180deg, var(--bg0), var(--bg1));
      min-height: 100vh;
    }

    .wrap {
      max-width: 1100px;
      margin: 0 auto;
      padding: 20px 16px 50px;
    }

    .hero {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 14px;
      align-items: center;
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 14px;
      background: linear-gradient(160deg, rgba(13,32,44,0.88), rgba(8,18,26,0.86));
      box-shadow: 0 12px 28px rgba(0, 0, 0, 0.3);
    }

    .brand {
      display: flex;
      gap: 12px;
      align-items: center;
    }

    .logo {
      width: 54px;
      height: 54px;
      border: 1px solid rgba(124,246,255,0.45);
      border-radius: 14px;
      display: grid;
      place-items: center;
      background: linear-gradient(140deg, rgba(124,246,255,0.22), rgba(102,243,166,0.18));
      color: var(--ink);
      font-family: var(--mono);
      font-size: 13px;
      letter-spacing: 0.5px;
      font-weight: 700;
    }

    .title {
      margin: 0;
      font-size: 24px;
      letter-spacing: 0.2px;
    }

    .subtitle {
      margin: 4px 0 0;
      color: var(--muted);
      font-size: 13px;
    }

    .actions {
      display: flex;
      gap: 10px;
      align-items: center;
      flex-wrap: wrap;
      justify-content: end;
    }

    button, .btn-link {
      border: 1px solid var(--line);
      border-radius: 11px;
      padding: 9px 12px;
      color: var(--ink);
      background: rgba(124,246,255,0.14);
      cursor: pointer;
      font-family: var(--sans);
      font-weight: 700;
      text-decoration: none;
      font-size: 13px;
    }

    button:hover, .btn-link:hover {
      background: rgba(124,246,255,0.23);
    }

    button:disabled { opacity: 0.6; cursor: not-allowed; }

    .status {
      margin-top: 12px;
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 9px 11px;
      font-family: var(--mono);
      font-size: 12px;
      color: var(--muted);
      background: rgba(255,255,255,0.03);
    }

    .monitor {
      margin-top: 12px;
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 14px;
      background: var(--panel);
      position: relative;
      overflow: hidden;
    }

    .monitor::before {
      content: "";
      position: absolute;
      inset: 0;
      pointer-events: none;
      background: repeating-linear-gradient(
        to bottom,
        rgba(124,246,255,0.04) 0,
        rgba(124,246,255,0.04) 1px,
        transparent 1px,
        transparent 6px
      );
      opacity: 0.45;
    }

    .monitor h2 {
      margin: 0;
      font-size: 14px;
      font-family: var(--mono);
      letter-spacing: 0.8px;
      color: var(--accent);
      text-transform: uppercase;
    }

    .cards {
      margin-top: 12px;
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
      position: relative;
      z-index: 1;
    }

    .card {
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 10px;
      background: rgba(255,255,255,0.03);
      min-height: 128px;
    }

    .card h3 {
      margin: 0;
      font-size: 12px;
      color: var(--muted);
      font-family: var(--mono);
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }

    .card .main {
      margin-top: 10px;
      font-size: 22px;
      font-weight: 800;
      letter-spacing: 0.2px;
    }

    .flag {
      margin-top: 6px;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 3px 8px;
      font-family: var(--mono);
      font-size: 11px;
    }

    .flag.ok { color: var(--ok); border-color: rgba(102,243,166,0.42); }
    .flag.warn { color: var(--warn); border-color: rgba(255,209,102,0.42); }
    .flag.err { color: var(--err); border-color: rgba(255,124,139,0.42); }

    .small {
      margin-top: 8px;
      font-size: 12px;
      color: var(--muted);
      line-height: 1.35;
      word-break: break-word;
    }

    .repos {
      margin-top: 8px;
      display: grid;
      gap: 5px;
      font-family: var(--mono);
      font-size: 11px;
      color: var(--muted);
    }

    .repo-row {
      display: flex;
      justify-content: space-between;
      gap: 8px;
    }

    .repo-row .ok { color: var(--ok); }
    .repo-row .idle { color: var(--muted); }

    .details {
      margin-top: 14px;
    }

    .details-head {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 8px;
    }

    .details-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
    }

    .panel {
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 10px;
      background: rgba(255,255,255,0.03);
    }

    .panel h4 {
      margin: 0;
      font-size: 13px;
    }

    .kv { margin-top: 8px; display: grid; gap: 5px; }
    .kv .row {
      display: flex;
      justify-content: space-between;
      gap: 8px;
      font-size: 12px;
      border-bottom: 1px dashed rgba(233,248,255,0.12);
      padding-bottom: 4px;
    }
    .kv .row:last-child { border-bottom: none; }
    .k { color: var(--muted); font-family: var(--mono); }
    .v { text-align: right; word-break: break-word; }

    .events { margin-top: 8px; display: grid; gap: 8px; max-height: 420px; overflow: auto; }
    .evt {
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 9px;
      background: rgba(255,255,255,0.02);
    }
    .evt-top { display: flex; justify-content: space-between; gap: 8px; }
    .evt-title { font-size: 13px; font-weight: 700; }
    .evt-badge {
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 2px 8px;
      font-size: 11px;
      font-family: var(--mono);
      color: var(--muted);
      white-space: nowrap;
    }
    .evt-meta {
      margin-top: 6px;
      font-size: 12px;
      color: var(--muted);
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      word-break: break-all;
    }

    a { color: #9fffcf; text-decoration: none; }
    a:hover { text-decoration: underline; }

    @media (max-width: 980px) {
      .hero { grid-template-columns: 1fr; }
      .actions { justify-content: start; }
      .cards { grid-template-columns: 1fr; }
      .details-grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <div class=\"wrap\">
    <header class=\"hero\">
      <div class=\"brand\">
        <div class=\"logo\">DSV4</div>
        <div>
          <h1 class=\"title\">DeepSeekV4 Spotter</h1>
          <p class=\"subtitle\">Realtime monitor for DeepSeek v4 signals from official site and selected GitHub repos.</p>
        </div>
      </div>
      <div class=\"actions\">
        <button id=\"pollBtn\">Run Poll Now</button>
        <button id=\"toggleBtn\">Open Detailed Panel</button>
      </div>
    </header>

    <div id=\"statusLine\" class=\"status\">loading...</div>

    <section class=\"monitor\">
      <h2>Signal Monitor</h2>
      <div class=\"cards\">
        <article class=\"card\">
          <h3>Official Site</h3>
          <div class=\"main\" id=\"officialModel\">n/a</div>
          <div class=\"flag\" id=\"officialFlag\">waiting</div>
          <div class=\"small\" id=\"officialNote\">Baseline target: v3.2</div>
        </article>

        <article class=\"card\">
          <h3>GitHub Track</h3>
          <div class=\"main\" id=\"ghMain\">0</div>
          <div class=\"flag\" id=\"ghFlag\">waiting</div>
          <div class=\"repos\" id=\"repoRows\"></div>
        </article>

        <article class=\"card\">
          <h3>Alert Engine</h3>
          <div class=\"main\" id=\"alertMain\">idle</div>
          <div class=\"flag\" id=\"alertFlag\">no trigger</div>
          <div class=\"small\" id=\"alertNote\">Webhook + audio will fire when v4 signal appears.</div>
        </article>
      </div>
    </section>

    <section class=\"details\" id=\"details\" hidden>
      <div class=\"details-head\">
        <strong>Detailed Panel</strong>
        <div>
          <a class=\"btn-link\" href=\"/api/config\" target=\"_blank\" rel=\"noreferrer\">/api/config</a>
          <a class=\"btn-link\" href=\"/api/events\" target=\"_blank\" rel=\"noreferrer\">/api/events</a>
        </div>
      </div>

      <div class=\"details-grid\">
        <section class=\"panel\">
          <h4>Runtime Config</h4>
          <div class=\"kv\" id=\"cfgRows\"></div>
        </section>

        <section class=\"panel\">
          <h4>Last Poll Snapshot</h4>
          <div class=\"kv\" id=\"pollRows\"></div>
        </section>
      </div>

      <section class=\"panel\" style=\"margin-top:10px\">
        <h4>Event Stream</h4>
        <div class=\"events\" id=\"events\"></div>
      </section>
    </section>
  </div>

<script>
const state = {
  cfg: null,
  poll: null,
  events: [],
};

const BASELINE_MODEL = 'v3.2';

async function getJSON(url, opts) {
  const r = await fetch(url, opts);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return await r.json();
}

function fmtTime(iso) {
  if (!iso) return 'n/a';
  try { return new Date(iso).toLocaleString(); } catch { return iso; }
}

function findLatestHomepageModel() {
  return state.events.find((e) => e.source === 'deepseek_homepage' && e.kind === 'homepage_model') || null;
}

function githubSignals() {
  return state.events.filter((e) => e.source === 'github_watch' && e.kind === 'github_v4_signal');
}

function clsFor(boolLike) {
  return boolLike ? 'ok' : 'warn';
}

function renderTop() {
  const s = document.getElementById('statusLine');
  const now = new Date().toLocaleString();
  s.textContent = `provider=${state.cfg?.provider || 'deepseek'} | events=${state.events.length} | refreshed=${now}`;
}

function renderOfficial() {
  const latest = findLatestHomepageModel();
  const model = latest?.payload?.chosen || 'n/a';
  const changed = model !== 'n/a' && model.toLowerCase() !== BASELINE_MODEL;

  document.getElementById('officialModel').textContent = model;

  const flag = document.getElementById('officialFlag');
  flag.className = `flag ${changed ? 'err' : 'ok'}`;
  flag.textContent = changed ? 'changed from baseline' : 'stable baseline';

  document.getElementById('officialNote').textContent =
    `Baseline=${BASELINE_MODEL}, last_fetch=${fmtTime(latest?.fetched_at)}`;
}

function renderGithub() {
  const rows = document.getElementById('repoRows');
  rows.innerHTML = '';

  const cfgRepos = state.cfg?.watch_github_repos || [];
  const signals = githubSignals();
  const touched = new Set(signals.map((e) => e.payload?.repo).filter(Boolean));

  document.getElementById('ghMain').textContent = String(signals.length);

  const hasSignal = signals.length > 0;
  const flag = document.getElementById('ghFlag');
  flag.className = `flag ${hasSignal ? 'warn' : 'ok'}`;
  flag.textContent = hasSignal ? 'new v4 signal found' : 'no v4 signal yet';

  for (const repo of cfgRepos) {
    const line = document.createElement('div');
    line.className = 'repo-row';

    const left = document.createElement('span');
    left.textContent = repo;

    const right = document.createElement('span');
    const yes = touched.has(repo);
    right.className = yes ? 'ok' : 'idle';
    right.textContent = yes ? 'signal' : 'no change';

    line.appendChild(left);
    line.appendChild(right);
    rows.appendChild(line);
  }
}

function renderAlert() {
  const a = state.poll?.alert || null;

  const main = document.getElementById('alertMain');
  const flag = document.getElementById('alertFlag');
  const note = document.getElementById('alertNote');

  if (!a) {
    main.textContent = 'idle';
    flag.className = 'flag warn';
    flag.textContent = 'no trigger';
    note.textContent = 'Webhook + audio will fire when v4 signal appears.';
    return;
  }

  main.textContent = a.signal || 'triggered';
  const ok = a.webhook?.ok === true || a.audio?.ok === true;
  flag.className = `flag ${ok ? 'ok' : 'warn'}`;
  flag.textContent = ok ? 'action done' : 'triggered with partial result';

  const wk = a.webhook?.ok === true ? 'ok' : a.webhook?.ok === false ? 'failed' : 'n/a';
  const ad = a.audio?.ok === true ? 'ok' : a.audio?.ok === false ? 'failed' : 'n/a';
  note.textContent = `webhook=${wk}, audio=${ad}`;
}

function kvRow(k, v) {
  const row = document.createElement('div');
  row.className = 'row';
  const kk = document.createElement('span');
  kk.className = 'k';
  kk.textContent = k;
  const vv = document.createElement('span');
  vv.className = 'v';
  vv.textContent = String(v ?? 'n/a');
  row.appendChild(kk);
  row.appendChild(vv);
  return row;
}

function renderDetail() {
  const cfg = document.getElementById('cfgRows');
  cfg.innerHTML = '';
  if (state.cfg) {
    cfg.appendChild(kvRow('provider', state.cfg.provider));
    cfg.appendChild(kvRow('poll_interval', `${state.cfg.poll_interval_seconds}s`));
    cfg.appendChild(kvRow('homepage', state.cfg.homepage_url));
    cfg.appendChild(kvRow('repos', (state.cfg.watch_github_repos || []).join(', ')));
    cfg.appendChild(kvRow('regex', state.cfg.watch_deepseek_v4_regex));
    cfg.appendChild(kvRow('webhook', state.cfg.feishu_webhook_enabled ? 'enabled' : 'disabled'));
    cfg.appendChild(kvRow('audio', state.cfg.audio_enabled ? 'enabled' : 'disabled'));
    cfg.appendChild(kvRow('alert_once', state.cfg.alert_once ? 'on' : 'off'));
  }

  const poll = document.getElementById('pollRows');
  poll.innerHTML = '';
  const p = state.poll;
  if (!p) {
    poll.appendChild(kvRow('last_poll', 'not run in this session'));
  } else {
    const hp = p.homepage || {};
    const gh = p.github_watch || {};
    poll.appendChild(kvRow('homepage_prev', hp.prev_model || 'n/a'));
    poll.appendChild(kvRow('homepage_new', hp.new_model || 'n/a'));
    poll.appendChild(kvRow('homepage_v4_transition', hp.v4_transition ? 'yes' : 'no'));
    poll.appendChild(kvRow('github_matched', gh.matched ?? 0));
    poll.appendChild(kvRow('github_new_signals', (gh.new_signals || []).length));
    poll.appendChild(kvRow('alert_triggered', p.alert ? 'yes' : 'no'));
    if (p.alert?.signal) poll.appendChild(kvRow('alert_signal', p.alert.signal));
  }
}

function renderEvents() {
  const box = document.getElementById('events');
  box.innerHTML = '';

  if (!state.events.length) {
    const n = document.createElement('div');
    n.className = 'evt';
    n.textContent = 'No events yet.';
    box.appendChild(n);
    return;
  }

  for (const e of state.events) {
    const card = document.createElement('div');
    card.className = 'evt';

    const top = document.createElement('div');
    top.className = 'evt-top';

    const title = document.createElement('div');
    title.className = 'evt-title';
    title.textContent = e.title || '(no title)';

    const badge = document.createElement('span');
    badge.className = 'evt-badge';
    badge.textContent = `${e.source || '?'}:${e.kind || '?'}`;

    top.appendChild(title);
    top.appendChild(badge);

    const meta = document.createElement('div');
    meta.className = 'evt-meta';
    meta.appendChild(document.createTextNode(`published: ${fmtTime(e.published_at)}`));
    meta.appendChild(document.createTextNode(`fetched: ${fmtTime(e.fetched_at)}`));

    if (e.url) {
      const a = document.createElement('a');
      a.href = e.url;
      a.target = '_blank';
      a.rel = 'noreferrer';
      a.textContent = e.url;
      meta.appendChild(a);
    }

    card.appendChild(top);
    card.appendChild(meta);
    box.appendChild(card);
  }
}

function renderAll() {
  renderTop();
  renderOfficial();
  renderGithub();
  renderAlert();
  renderDetail();
  renderEvents();
}

async function loadConfig() {
  try { state.cfg = await getJSON('/api/config'); } catch (_) { state.cfg = null; }
}

async function loadEvents() {
  const data = await getJSON('/api/events?limit=80');
  state.events = data.events || [];
}

async function pollNow() {
  const btn = document.getElementById('pollBtn');
  btn.disabled = true;
  btn.textContent = 'Polling...';
  try {
    state.poll = await getJSON('/api/poll', { method: 'POST' });
  } catch (_) {
    // keep previous snapshot
  } finally {
    try { await loadEvents(); } catch (_) {}
    renderAll();
    btn.disabled = false;
    btn.textContent = 'Run Poll Now';
  }
}

function setupToggle() {
  const btn = document.getElementById('toggleBtn');
  const details = document.getElementById('details');
  btn.addEventListener('click', () => {
    details.hidden = !details.hidden;
    btn.textContent = details.hidden ? 'Open Detailed Panel' : 'Hide Detailed Panel';
  });
}

async function boot() {
  await Promise.all([loadConfig(), loadEvents()]);
  setupToggle();
  renderAll();
}

document.getElementById('pollBtn').addEventListener('click', pollNow);
boot();
</script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    server_version = "DeepSeekTrackerLite/0.1"

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        p = urlparse(self.path)
        if p.path == "/":
            self._send(200, _HTML.encode("utf-8"), "text/html; charset=utf-8")
            return

        if p.path == "/api/config":
            s = get_settings()
            payload = {
                "provider": s.provider,
                "homepage_url": s.homepage_url,
                "poll_interval_seconds": s.poll_interval_seconds,
                "watch_github_repos": s.watch_github_repos,
                "watch_deepseek_v4_regex": s.watch_deepseek_v4_regex,
                "feishu_webhook_enabled": bool(s.feishu_webhook_url),
                "audio_enabled": bool(s.alert_mp3_path),
                "audio_path": s.alert_mp3_path,
                "alert_loops": s.alert_loops,
                "alert_interval_seconds": s.alert_interval_seconds,
                "alert_once": s.alert_once,
            }
            body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
            self._send(200, body, "application/json; charset=utf-8")
            return

        if p.path == "/api/events":
            s = get_settings()
            qs = parse_qs(p.query or "")
            limit = 50
            try:
                if "limit" in qs:
                    limit = int(qs["limit"][0])
            except Exception:
                limit = 50

            with connect(s.db_path) as conn:
                init_db(conn)
                events = list_events(conn, provider=s.provider, limit=limit)

            body = json.dumps({"events": events}, ensure_ascii=True).encode("utf-8")
            self._send(200, body, "application/json; charset=utf-8")
            return

        self._send(404, b"not found", "text/plain; charset=utf-8")

    def do_POST(self) -> None:  # noqa: N802
        p = urlparse(self.path)
        if p.path == "/api/poll":
            res = poll_homepage_once()
            body = json.dumps(res, ensure_ascii=True).encode("utf-8")
            self._send(200, body, "application/json; charset=utf-8")
            return

        self._send(404, b"not found", "text/plain; charset=utf-8")

    def log_message(self, fmt: str, *args) -> None:
        return


def run(host: str = "127.0.0.1", port: int = 8000) -> None:
    s = get_settings()
    with connect(s.db_path) as conn:
        init_db(conn)

    def autopoll_loop() -> None:
        while True:
            s2 = get_settings()
            if s2.poll_interval_seconds == 0:
                return
            try:
                poll_homepage_once()
            except Exception:
                pass
            time.sleep(s2.poll_interval_seconds)

    if s.poll_interval_seconds != 0:
        t = threading.Thread(target=autopoll_loop, name="autopoll", daemon=True)
        t.start()

    httpd = HTTPServer((host, port), Handler)
    httpd.serve_forever()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--interval-seconds", type=int, default=None, help="Auto-poll interval; default 600; 0 disables")
    ap.add_argument("--feishu-webhook-url", default=None, help="If set, send webhook on v4 signals")
    args = ap.parse_args()

    if args.interval_seconds is not None:
        os.environ["POLL_INTERVAL_SECONDS"] = str(args.interval_seconds)
    if args.feishu_webhook_url:
        os.environ["FEISHU_WEBHOOK_URL"] = args.feishu_webhook_url

    run(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
