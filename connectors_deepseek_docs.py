from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional, Set, Tuple

import requests
from dateutil import parser as date_parser


_BASE = "https://api-docs.deepseek.com"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_id(*parts: str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update((p or "").encode("utf-8"))
        h.update(b"\0")
    return h.hexdigest()[:32]


def _abs_url(href: str) -> str:
    href = (href or "").strip()
    if not href:
        return ""
    if href.startswith("http://") or href.startswith("https://"):
        return href
    if href.startswith("/"):
        return _BASE.rstrip("/") + href
    return _BASE.rstrip("/") + "/" + href


_NEWS_PATH_RE = re.compile(r"^/zh-cn/news/news\d+$")


class _LinkExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        if tag.lower() != "a":
            return
        for k, v in attrs:
            if k.lower() == "href" and v:
                self.hrefs.append(v)


class _H1Extractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._in_h1 = False
        self._chunks: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        if tag.lower() == "h1":
            self._in_h1 = True

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "h1":
            self._in_h1 = False

    def handle_data(self, data: str) -> None:
        if self._in_h1 and data:
            self._chunks.append(data.strip())

    def get_text(self) -> str:
        return " ".join([c for c in self._chunks if c]).strip()


def _parse_date_from_text(text: str) -> Optional[str]:
    # Common patterns we might see in Chinese docs pages.
    m = re.search(r"(20\d{2}[-/.]?(0[1-9]|1[0-2])[-/.]?([0-2]\d|3[01]))", text)
    if not m:
        return None
    s = m.group(1)
    # Normalize separators.
    s = s.replace(".", "-").replace("/", "-")
    if re.fullmatch(r"20\d{2}(0[1-9]|1[0-2])([0-2]\d|3[01])", s):
        s = f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
    try:
        dt = date_parser.parse(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except Exception:
        return None


def _looks_like_login_gate(html: str) -> bool:
    # Heuristic: if the page contains common login prompts.
    needles = [
        "扫码",
        "微信",
        "验证码",
        "手机号",
        "登录",
        "login",
        "sign in",
    ]
    lower = html.lower()
    return any(n in html for n in needles[:5]) or any(n in lower for n in needles[5:])


def fetch_deepseek_docs_news(
    *,
    seed_urls: List[str],
    provider: str,
    cookie: Optional[str] = None,
    fetch_limit: int = 0,
    timeout_s: float = 20.0,
) -> List[Dict[str, Any]]:
    """Discover DeepSeek docs news pages by parsing seed pages.

    If fetch_limit > 0, also fetch up to that many discovered pages to extract <h1> title and a date.

    Auth note:
    - If the docs site is gated, you can pass a raw Cookie header string via DEEPSEEK_DOCS_COOKIE.
    """

    events: List[Dict[str, Any]] = []

    sess = requests.Session()
    sess.headers.update(
        {
            "User-Agent": "deepseek-tracker-demo/0.1",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
    )
    if cookie:
        sess.headers["Cookie"] = cookie

    discovered: Set[str] = set()

    for seed in seed_urls:
        seed = (seed or "").strip()
        if not seed:
            continue

        try:
            resp = sess.get(seed, timeout=timeout_s, allow_redirects=True)
            resp.raise_for_status()
            html = resp.text or ""
        except Exception as e:
            events.append(
                {
                    "provider": provider,
                    "kind": "source_error",
                    "source": "deepseek_docs",
                    "source_id": f"error:{_hash_id(seed)}",
                    "title": f"DeepSeek docs fetch failed: {type(e).__name__}",
                    "url": seed,
                    "published_at": None,
                    "fetched_at": _now_iso(),
                    "payload": {"seed": seed, "error": str(e)},
                }
            )
            continue

        if _looks_like_login_gate(html):
            events.append(
                {
                    "provider": provider,
                    "kind": "auth_required",
                    "source": "deepseek_docs",
                    "source_id": f"auth:{_hash_id(seed)}",
                    "title": "DeepSeek docs appears to require login (set DEEPSEEK_DOCS_COOKIE)",
                    "url": seed,
                    "published_at": None,
                    "fetched_at": _now_iso(),
                    "payload": {"seed": seed, "hint": "Open the page in browser, login, copy request Cookie header."},
                }
            )
            continue

        p = _LinkExtractor()
        try:
            p.feed(html)
        except Exception:
            # If HTML is malformed, fall back to regex.
            hrefs = re.findall(r"href=\"([^\"]+)\"", html)
            p.hrefs = hrefs

        for href in p.hrefs:
            href = (href or "").strip()
            if not href:
                continue

            # Normalize and filter to /zh-cn/news/newsNNNNNN.
            if href.startswith(_BASE):
                path = href[len(_BASE) :]
            else:
                path = href

            if path.startswith("http"):
                # other domains
                continue

            if path.startswith("/") and _NEWS_PATH_RE.match(path):
                discovered.add(_abs_url(path))

        # Also ensure the seed itself becomes a tracked item if it matches.
        if seed.startswith(_BASE) and _NEWS_PATH_RE.match(seed[len(_BASE) :]):
            discovered.add(seed)

    # Create events for discovered pages.
    urls = sorted(discovered)
    for u in urls:
        path = u[len(_BASE) :] if u.startswith(_BASE) else u
        events.append(
            {
                "provider": provider,
                "kind": "news_page",
                "source": "deepseek_docs",
                "source_id": f"news:{path}",
                "title": f"DeepSeek docs news: {path}",
                "url": u,
                "published_at": None,
                "fetched_at": _now_iso(),
                "payload": {"path": path, "discovered_via": "seed"},
            }
        )

    # Optional: fetch a subset to extract title and date, emitting "news_detail" events.
    if fetch_limit and urls:
        for u in urls[:fetch_limit]:
            try:
                resp = sess.get(u, timeout=timeout_s, allow_redirects=True)
                resp.raise_for_status()
                html = resp.text or ""
            except Exception as e:
                events.append(
                    {
                        "provider": provider,
                        "kind": "source_error",
                        "source": "deepseek_docs",
                        "source_id": f"detail_error:{_hash_id(u)}",
                        "title": f"DeepSeek docs detail fetch failed: {type(e).__name__}",
                        "url": u,
                        "published_at": None,
                        "fetched_at": _now_iso(),
                        "payload": {"url": u, "error": str(e)},
                    }
                )
                continue

            h1p = _H1Extractor()
            try:
                h1p.feed(html)
            except Exception:
                pass
            h1 = h1p.get_text() or "(no h1)"
            pub = _parse_date_from_text(html)

            path = u[len(_BASE) :] if u.startswith(_BASE) else u
            events.append(
                {
                    "provider": provider,
                    "kind": "news_detail",
                    "source": "deepseek_docs",
                    "source_id": f"detail:{path}",
                    "title": f"{h1}",
                    "url": u,
                    "published_at": pub,
                    "fetched_at": _now_iso(),
                    "payload": {"path": path, "extracted_h1": h1},
                }
            )

    return events
