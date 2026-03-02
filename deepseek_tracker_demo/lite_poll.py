from __future__ import annotations

import json
import re
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .audio_alert import play_mp3_loop
from .config import get_settings
from .db import connect, get_latest_homepage_model, has_alert_fired, init_db, insert_events
from .github_watch import find_deepseek_v4_signals
from .notify_feishu import send_feishu_webhook


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


_VERSION_RE = re.compile(r"\bv\d+(?:\.\d+)*\b", re.IGNORECASE)


def _version_key(v: str) -> Tuple[int, ...]:
    v = v.strip().lower()
    if v.startswith("v"):
        v = v[1:]
    out: List[int] = []
    for p in v.split("."):
        try:
            out.append(int(p))
        except ValueError:
            out.append(0)
    return tuple(out)


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
    uniq = sorted(set([c.lower() for c in candidates]), key=_version_key)
    return uniq[-1]


def _fetch_html(url: str, *, timeout_s: float = 15.0) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "deepseek-tracker-demo/0.2",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        raw = resp.read()
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return raw.decode("utf-8", errors="replace")


def _is_v4(model: Optional[str]) -> bool:
    if not model:
        return False
    m = model.strip().lower()
    return m == "v4" or m.startswith("v4.")


def _fire_v4_alert(
    *,
    provider: str,
    prev_model: Optional[str],
    new_model: str,
    signal: str,
    evidence: Dict[str, Any],
) -> Dict[str, Any]:
    """Send Feishu webhook + play MP3 (best-effort)."""

    s = get_settings()

    if s.alert_once:
        with connect(s.db_path) as conn:
            init_db(conn)
            if has_alert_fired(conn, provider=provider, alert_key="v4"):
                return {"skipped": True, "reason": "alert_once"}

    webhook = {"enabled": bool(s.feishu_webhook_url), "attempted": False, "ok": None, "detail": None}
    if s.feishu_webhook_url:
        webhook["attempted"] = True
        ok, detail = send_feishu_webhook(
            webhook_url=s.feishu_webhook_url,
            payload={
                "provider": provider,
                "signal": signal,
                "prev_model": prev_model,
                "new_model": new_model,
                "evidence": evidence,
                "detected_at": _now_iso(),
            },
        )
        webhook["ok"] = ok
        webhook["detail"] = detail

        audit_event = {
            "provider": provider,
            "kind": "webhook_sent" if ok else "webhook_failed",
            "source": "feishu",
            "source_id": f"v4:{_now_iso()}",
            "title": f"Feishu webhook {'sent' if ok else 'failed'} for v4 signal ({signal})",
            "url": s.feishu_webhook_url,
            "published_at": None,
            "fetched_at": _now_iso(),
            "payload": {
                "signal": signal,
                "prev_model": prev_model,
                "new_model": new_model,
                "detail": detail,
                "evidence": evidence,
            },
        }
        with connect(s.db_path) as conn:
            init_db(conn)
            insert_events(conn, [audit_event])

    audio = {"enabled": bool(s.alert_mp3_path), "attempted": False, "ok": None, "detail": None}
    if s.alert_mp3_path:
        audio["attempted"] = True
        ok, detail = play_mp3_loop(
            mp3_path=s.alert_mp3_path,
            loops=s.alert_loops,
            interval_seconds=s.alert_interval_seconds,
        )
        audio["ok"] = ok
        audio["detail"] = detail

        audit_event = {
            "provider": provider,
            "kind": "audio_played" if ok else "audio_failed",
            "source": "audio",
            "source_id": f"v4:{_now_iso()}",
            "title": f"Audio alert {'played' if ok else 'failed'} for v4 signal ({signal})",
            "url": s.alert_mp3_path,
            "published_at": None,
            "fetched_at": _now_iso(),
            "payload": {
                "signal": signal,
                "new_model": new_model,
                "loops": s.alert_loops,
                "interval_seconds": s.alert_interval_seconds,
                "detail": detail,
                "evidence": evidence,
            },
        }
        with connect(s.db_path) as conn:
            init_db(conn)
            insert_events(conn, [audit_event])

    if s.alert_once:
        fired_event = {
            "provider": provider,
            "kind": "alert_fired",
            "source": "system",
            "source_id": "v4",
            "title": f"v4 alert fired ({signal})",
            "url": None,
            "published_at": None,
            "fetched_at": _now_iso(),
            "payload": {
                "signal": signal,
                "prev_model": prev_model,
                "new_model": new_model,
                "evidence": evidence,
                "webhook": webhook,
                "audio": audio,
            },
        }
        with connect(s.db_path) as conn:
            init_db(conn)
            insert_events(conn, [fired_event])

    return {"skipped": False, "signal": signal, "webhook": webhook, "audio": audio}


def poll_once() -> Dict[str, Any]:
    s = get_settings()

    # 1) Homepage model signal
    url = s.homepage_url
    homepage_events: List[Dict[str, Any]] = []
    chosen: Optional[str] = None

    with connect(s.db_path) as conn:
        init_db(conn)
        prev = get_latest_homepage_model(conn, provider=s.provider)
    prev_model = (prev or {}).get("chosen")

    try:
        html = _fetch_html(url)
    except Exception as e:
        homepage_events.append(
            {
                "provider": s.provider,
                "kind": "source_error",
                "source": "deepseek_homepage",
                "source_id": f"error:{url}",
                "title": f"DeepSeek homepage fetch failed: {type(e).__name__}",
                "url": url,
                "published_at": None,
                "fetched_at": _now_iso(),
                "payload": {"url": url, "error": str(e)},
            }
        )
        best_next = None
        best_raw = None
    else:
        next_found = _extract_versions_from_next_data(html)
        best_next = _pick_best_version([v for _p, v in next_found])
        best_raw = _pick_best_version([m.group(0) for m in _VERSION_RE.finditer(html)])
        chosen = best_next or best_raw

    if chosen:
        homepage_events.append(
            {
                "provider": s.provider,
                "kind": "homepage_model",
                "source": "deepseek_homepage",
                "source_id": f"model:{chosen.lower()}",
                "title": f"DeepSeek homepage model: {chosen}",
                "url": url,
                "published_at": None,
                "fetched_at": _now_iso(),
                "payload": {"chosen": chosen, "best_next": best_next, "best_raw": best_raw},
            }
        )
    else:
        homepage_events.append(
            {
                "provider": s.provider,
                "kind": "no_signal",
                "source": "deepseek_homepage",
                "source_id": f"nosignal:{url}",
                "title": "DeepSeek homepage: no version token found",
                "url": url,
                "published_at": None,
                "fetched_at": _now_iso(),
                "payload": {"url": url},
            }
        )

    with connect(s.db_path) as conn:
        init_db(conn)
        homepage_inserted = insert_events(conn, homepage_events)

    v4_transition = _is_v4(chosen) and not _is_v4(prev_model)

    # 2) GitHub v4 signals (watch repos like vllm)
    gh_events = find_deepseek_v4_signals(
        provider=s.provider,
        repos=s.watch_github_repos,
        token=s.github_token,
        pattern=s.watch_deepseek_v4_regex,
    )

    new_gh_signals: List[Dict[str, Any]] = []
    gh_inserted = 0
    with connect(s.db_path) as conn:
        init_db(conn)
        for ev in gh_events:
            ins = insert_events(conn, [ev])
            if ins == 1:
                gh_inserted += 1
                if ev.get("kind") == "github_v4_signal":
                    new_gh_signals.append(ev)

    alert: Optional[Dict[str, Any]] = None
    # Prefer the definitive homepage transition, otherwise alert on the first new GitHub signal.
    if v4_transition:
        alert = _fire_v4_alert(
            provider=s.provider,
            prev_model=prev_model,
            new_model=chosen or "v4",
            signal="homepage_model_v4",
            evidence={"source": "deepseek_homepage", "url": url, "prev_model": prev_model, "new_model": chosen},
        )
    elif new_gh_signals:
        alert = _fire_v4_alert(
            provider=s.provider,
            prev_model=prev_model,
            new_model="v4",
            signal="github_v4_signal",
            evidence={"source": "github_watch", "event": new_gh_signals[0]},
        )

    return {
        "provider": s.provider,
        "db_path": s.db_path,
        "homepage": {
            "url": url,
            "prev_model": prev_model,
            "new_model": chosen,
            "v4_transition": v4_transition,
            "inserted": homepage_inserted,
        },
        "github_watch": {
            "repos": s.watch_github_repos,
            "matched": len([e for e in gh_events if e.get("kind") == "github_v4_signal"]),
            "inserted": gh_inserted,
            "new_signals": new_gh_signals,
        },
        "alert": alert,
    }


def poll_homepage_once() -> Dict[str, Any]:
    # Backward-compatible entrypoint used by lite_server.
    return poll_once()


def main() -> None:
    import json

    print(json.dumps(poll_once(), ensure_ascii=True))


if __name__ == "__main__":
    main()
