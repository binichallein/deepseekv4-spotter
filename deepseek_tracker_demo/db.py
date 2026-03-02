from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, List, Optional


SCHEMA_SQL = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  provider TEXT NOT NULL,
  kind TEXT NOT NULL,
  source TEXT NOT NULL,
  source_id TEXT NOT NULL,
  title TEXT NOT NULL,
  url TEXT,
  published_at TEXT,
  fetched_at TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  UNIQUE(source, source_id)
);

CREATE INDEX IF NOT EXISTS idx_events_provider_published
  ON events(provider, published_at);

CREATE INDEX IF NOT EXISTS idx_events_fetched_at
  ON events(fetched_at);
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def connect(db_path: str) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(db_path)
    try:
        conn.row_factory = sqlite3.Row
        yield conn
    finally:
        conn.close()


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)
    conn.commit()


def insert_events(
    conn: sqlite3.Connection,
    events: List[Dict[str, Any]],
) -> int:
    """Insert events, ignoring duplicates by (source, source_id)."""

    cur = conn.cursor()
    inserted = 0

    for e in events:
        fetched_at = e.get("fetched_at") or _now_iso()
        payload_json = json.dumps(e.get("payload") or {}, ensure_ascii=True, sort_keys=True)

        try:
            cur.execute(
                """
                INSERT INTO events (
                  provider, kind, source, source_id, title, url, published_at, fetched_at, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    e["provider"],
                    e["kind"],
                    e["source"],
                    e["source_id"],
                    e["title"],
                    e.get("url"),
                    e.get("published_at"),
                    fetched_at,
                    payload_json,
                ),
            )
            inserted += 1
        except sqlite3.IntegrityError:
            # Duplicate (source, source_id)
            continue

    conn.commit()
    return inserted


def list_events(
    conn: sqlite3.Connection,
    provider: Optional[str] = None,
    limit: int = 50,
    since_published_at: Optional[str] = None,
) -> List[Dict[str, Any]]:
    limit = max(1, min(int(limit), 200))

    where = []
    params: List[Any] = []

    if provider:
        where.append("provider = ?")
        params.append(provider)

    if since_published_at:
        where.append("(published_at IS NOT NULL AND published_at >= ?)")
        params.append(since_published_at)

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    rows = conn.execute(
        f"""
        SELECT id, provider, kind, source, source_id, title, url, published_at, fetched_at, payload_json
        FROM events
        {where_sql}
        ORDER BY COALESCE(published_at, fetched_at) DESC
        LIMIT ?
        """,
        (*params, limit),
    ).fetchall()

    out: List[Dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "id": r["id"],
                "provider": r["provider"],
                "kind": r["kind"],
                "source": r["source"],
                "source_id": r["source_id"],
                "title": r["title"],
                "url": r["url"],
                "published_at": r["published_at"],
                "fetched_at": r["fetched_at"],
                "payload": json.loads(r["payload_json"]),
            }
        )

    return out


def get_latest_homepage_model(conn: sqlite3.Connection, *, provider: str) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        """
        SELECT id, url, fetched_at, payload_json, source_id
        FROM events
        WHERE provider = ?
          AND source = 'deepseek_homepage'
          AND kind = 'homepage_model'
        ORDER BY fetched_at DESC
        LIMIT 1
        """,
        (provider,),
    ).fetchone()
    if row is None:
        return None

    payload = json.loads(row["payload_json"])
    chosen = payload.get("chosen")
    if not chosen:
        sid = row["source_id"] or ""
        if sid.startswith("model:"):
            chosen = sid[len("model:") :]

    return {
        "id": row["id"],
        "url": row["url"],
        "fetched_at": row["fetched_at"],
        "chosen": chosen,
    }


def has_alert_fired(conn: sqlite3.Connection, *, provider: str, alert_key: str) -> bool:
    row = conn.execute(
        """
        SELECT 1
        FROM events
        WHERE provider = ?
          AND source = 'system'
          AND kind = 'alert_fired'
          AND source_id = ?
        LIMIT 1
        """,
        (provider, alert_key),
    ).fetchone()
    return row is not None
