from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests
from dateutil import parser as date_parser


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_text(el: Optional[ET.Element]) -> str:
    if el is None or el.text is None:
        return ""
    return el.text.strip()


def _pick_first_text(parent: ET.Element, tags: List[str]) -> str:
    for t in tags:
        el = parent.find(t)
        if el is not None:
            v = _safe_text(el)
            if v:
                return v
    return ""


def _parse_date(s: str) -> Optional[str]:
    s = (s or "").strip()
    if not s:
        return None
    try:
        dt = date_parser.parse(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except Exception:
        return None


def _hash_id(*parts: str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update((p or "").encode("utf-8"))
        h.update(b"\0")
    return h.hexdigest()[:32]


def fetch_rss(
    *,
    feeds: List[str],
    provider: str,
    timeout_s: float = 15.0,
) -> List[Dict[str, Any]]:
    """Very small RSS/Atom fetcher.

    For demo purposes: extracts title/link/date and generates a stable source_id.
    """

    events: List[Dict[str, Any]] = []

    sess = requests.Session()
    sess.headers.update({"User-Agent": "deepseek-tracker-demo/0.1"})

    for feed_url in feeds:
        feed_url = (feed_url or "").strip()
        if not feed_url:
            continue

        try:
            resp = sess.get(feed_url, timeout=timeout_s)
            resp.raise_for_status()
            xml = resp.text
            root = ET.fromstring(xml)
        except Exception as e:
            events.append(
                {
                    "provider": provider,
                    "kind": "source_error",
                    "source": "rss",
                    "source_id": f"error:{_hash_id(feed_url)}",
                    "title": f"RSS fetch failed: {type(e).__name__}",
                    "url": feed_url,
                    "published_at": None,
                    "fetched_at": _now_iso(),
                    "payload": {"feed": feed_url, "error": str(e)},
                }
            )
            continue

        # RSS: <rss><channel><item>...
        channel = root.find("channel")
        if channel is not None:
            items = channel.findall("item")
            for it in items:
                title = _pick_first_text(it, ["title"]) or "(no title)"
                link = _pick_first_text(it, ["link"]) or None
                guid = _pick_first_text(it, ["guid"]) or ""
                pub = _parse_date(_pick_first_text(it, ["pubDate"]))

                sid = _hash_id(feed_url, guid or "", link or "", title)
                events.append(
                    {
                        "provider": provider,
                        "kind": "post",
                        "source": "rss",
                        "source_id": sid,
                        "title": title,
                        "url": link,
                        "published_at": pub,
                        "fetched_at": _now_iso(),
                        "payload": {"feed": feed_url, "guid": guid},
                    }
                )
            continue

        # Atom: <feed><entry>...
        # Atom commonly uses namespaces; do a namespace-agnostic scan.
        entries: List[ET.Element] = []
        for el in root.iter():
            if el.tag.endswith("entry"):
                entries.append(el)

        for ent in entries:
            title = "(no title)"
            for el in ent.iter():
                if el.tag.endswith("title") and _safe_text(el):
                    title = _safe_text(el)
                    break

            link = None
            for el in ent.iter():
                if el.tag.endswith("link"):
                    href = el.attrib.get("href")
                    if href:
                        link = href.strip()
                        break

            updated = None
            for el in ent.iter():
                if el.tag.endswith("updated") and _safe_text(el):
                    updated = _parse_date(_safe_text(el))
                    break

            eid = ""
            for el in ent.iter():
                if el.tag.endswith("id") and _safe_text(el):
                    eid = _safe_text(el)
                    break

            sid = _hash_id(feed_url, eid or "", link or "", title)
            events.append(
                {
                    "provider": provider,
                    "kind": "post",
                    "source": "rss",
                    "source_id": sid,
                    "title": title,
                    "url": link,
                    "published_at": updated,
                    "fetched_at": _now_iso(),
                    "payload": {"feed": feed_url, "entry_id": eid},
                }
            )

    return events
