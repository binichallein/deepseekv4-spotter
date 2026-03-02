from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_id(*parts: str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update((p or "").encode("utf-8"))
        h.update(b"\0")
    return h.hexdigest()[:32]


_VERSION_RE = re.compile(r"\bv\d+(?:\.\d+)*\b", re.IGNORECASE)


def _version_key(v: str) -> Tuple[int, ...]:
    # "v3.2" -> (3,2)
    v = v.strip().lower()
    if v.startswith("v"):
        v = v[1:]
    parts = []
    for p in v.split("."):
        try:
            parts.append(int(p))
        except ValueError:
            parts.append(0)
    return tuple(parts)


class _NextDataExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._capture = False
        self._chunks: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        if tag.lower() != "script":
            return
        attr = {k.lower(): (v or "") for k, v in attrs}
        # Next.js commonly uses <script id="__NEXT_DATA__" type="application/json">...</script>
        if attr.get("id") == "__NEXT_DATA__" and "json" in attr.get("type", ""):
            self._capture = True

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "script" and self._capture:
            self._capture = False

    def handle_data(self, data: str) -> None:
        if self._capture and data:
            self._chunks.append(data)

    def get_json_text(self) -> str:
        return "".join(self._chunks).strip()


def _iter_strings(obj: Any, *, path: str = "") -> Iterable[Tuple[str, str]]:
    # yields (path, string)
    if isinstance(obj, str):
        yield (path, obj)
        return
    if isinstance(obj, list):
        for i, it in enumerate(obj):
            yield from _iter_strings(it, path=f"{path}[{i}]")
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            k2 = str(k)
            p2 = f"{path}.{k2}" if path else k2
            yield from _iter_strings(v, path=p2)
        return


def _extract_versions_from_next_data(html: str) -> List[Tuple[str, str]]:
    p = _NextDataExtractor()
    try:
        p.feed(html)
    except Exception:
        return []

    txt = p.get_json_text()
    if not txt:
        return []

    try:
        data = json.loads(txt)
    except Exception:
        return []

    found: List[Tuple[str, str]] = []
    for path, s in _iter_strings(data):
        for m in _VERSION_RE.finditer(s):
            found.append((path, m.group(0)))

    return found


def _pick_best_version(candidates: List[str]) -> Optional[str]:
    if not candidates:
        return None
    # Prefer the numerically largest version token.
    uniq = sorted(set([c.lower() for c in candidates]), key=_version_key)
    return uniq[-1]


def fetch_deepseek_homepage_model(
    *,
    homepage_url: str,
    provider: str,
    timeout_s: float = 15.0,
) -> List[Dict[str, Any]]:
    """Fetch DeepSeek homepage and extract the currently displayed model version.

    This is a best-effort signal. Many sites render via JS and may use anti-bot protections.
    """

    url = (homepage_url or "").strip()
    if not url:
        return []

    sess = requests.Session()
    sess.headers.update(
        {
            "User-Agent": "deepseek-tracker-demo/0.1",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
    )

    try:
        resp = sess.get(url, timeout=timeout_s, allow_redirects=True)
        status = resp.status_code
        html = resp.text or ""
    except Exception as e:
        return [
            {
                "provider": provider,
                "kind": "source_error",
                "source": "deepseek_homepage",
                "source_id": f"error:{_hash_id(url)}",
                "title": f"DeepSeek homepage fetch failed: {type(e).__name__}",
                "url": url,
                "published_at": None,
                "fetched_at": _now_iso(),
                "payload": {"url": url, "error": str(e)},
            }
        ]

    if status >= 400:
        return [
            {
                "provider": provider,
                "kind": "blocked",
                "source": "deepseek_homepage",
                "source_id": f"blocked:{status}:{_hash_id(url)}",
                "title": f"DeepSeek homepage returned HTTP {status}",
                "url": url,
                "published_at": None,
                "fetched_at": _now_iso(),
                "payload": {"url": url, "status": status},
            }
        ]

    # 1) Try Next.js embedded JSON (more structured; less false positives).
    next_found = _extract_versions_from_next_data(html)
    next_versions = [v for _path, v in next_found]
    best_next = _pick_best_version(next_versions)

    # 2) Fallback: regex over full HTML.
    raw_versions = [m.group(0) for m in _VERSION_RE.finditer(html)]
    best_raw = _pick_best_version(raw_versions)

    # Prefer Next.js-derived version when available.
    chosen = best_next or best_raw

    events: List[Dict[str, Any]] = []

    # Always emit a "signal" event so you can see what was extracted.
    if chosen:
        events.append(
            {
                "provider": provider,
                "kind": "homepage_model",
                "source": "deepseek_homepage",
                "source_id": f"model:{chosen.lower()}",
                "title": f"DeepSeek homepage model: {chosen}",
                "url": url,
                "published_at": None,
                "fetched_at": _now_iso(),
                "payload": {
                    "homepage_url": url,
                    "chosen": chosen,
                    "best_next": best_next,
                    "best_raw": best_raw,
                    "next_paths": list({p for p, _v in next_found})[:25],
                },
            }
        )
    else:
        events.append(
            {
                "provider": provider,
                "kind": "no_signal",
                "source": "deepseek_homepage",
                "source_id": f"nosignal:{_hash_id(url, html[:2048])}",
                "title": "DeepSeek homepage: no version token found",
                "url": url,
                "published_at": None,
                "fetched_at": _now_iso(),
                "payload": {"homepage_url": url},
            }
        )

    return events
