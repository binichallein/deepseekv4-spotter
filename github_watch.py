from __future__ import annotations

import json
import re
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _iso_or_none(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    return s.replace("Z", "+00:00")


def _fetch_json(url: str, *, token: Optional[str], timeout_s: float = 12.0) -> Any:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "deepseek-tracker-demo/0.2",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        raw = resp.read()

    # GitHub API responses are UTF-8 JSON.
    return json.loads(raw.decode("utf-8"))


def fetch_repo_events(
    *,
    repo: str,
    token: Optional[str],
    per_page: int = 30,
) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
    """Returns (events, error)."""

    per_page = max(1, min(int(per_page), 100))
    url = f"https://api.github.com/repos/{repo}/events?per_page={per_page}"

    try:
        data = _fetch_json(url, token=token)
    except Exception as e:
        return (None, f"fetch_failed:{type(e).__name__}:{e}")

    if not isinstance(data, list):
        return (None, "unexpected_response")

    out: List[Dict[str, Any]] = []
    for ev in data:
        if isinstance(ev, dict):
            out.append(ev)
    return (out, None)


def _best_event_url(repo: str, ev: Dict[str, Any], match_commit_sha: Optional[str]) -> Optional[str]:
    payload = ev.get("payload") or {}
    etype = ev.get("type") or ""

    if etype == "PullRequestEvent":
        pr = payload.get("pull_request") or {}
        return pr.get("html_url")

    if etype == "ReleaseEvent":
        rel = payload.get("release") or {}
        return rel.get("html_url")

    if etype == "PushEvent" and match_commit_sha:
        return f"https://github.com/{repo}/commit/{match_commit_sha}"

    # Fallback: repo itself.
    return f"https://github.com/{repo}"


def _first_line(s: str) -> str:
    return (s or "").splitlines()[0].strip()


def find_deepseek_v4_signals(
    *,
    provider: str,
    repos: List[str],
    token: Optional[str],
    pattern: str,
) -> List[Dict[str, Any]]:
    """Scan GitHub repo events and return normalized v4 signal events.

    Only inspects PushEvent / PullRequestEvent / ReleaseEvent.
    """

    try:
        rx = re.compile(pattern, re.IGNORECASE)
    except re.error:
        rx = re.compile(r"deepseek\s*[-_]?\s*v4(\b|\.)", re.IGNORECASE)

    out: List[Dict[str, Any]] = []

    for repo in repos:
        repo = (repo or "").strip()
        if not repo:
            continue

        events, err = fetch_repo_events(repo=repo, token=token)
        if err:
            out.append(
                {
                    "provider": provider,
                    "kind": "source_error",
                    "source": "github_watch",
                    "source_id": f"error:{repo}",
                    "title": f"GitHub watch failed for {repo}: {err}",
                    "url": f"https://github.com/{repo}",
                    "published_at": None,
                    "fetched_at": _now_iso(),
                    "payload": {"repo": repo, "error": err},
                }
            )
            continue

        assert events is not None
        for ev in events:
            ev_id = str(ev.get("id") or "").strip()
            if not ev_id:
                continue

            etype = ev.get("type") or ""
            actor = (ev.get("actor") or {}).get("login")
            created_at = _iso_or_none(ev.get("created_at"))
            payload = ev.get("payload") or {}

            match_text: Optional[str] = None
            match_where: Optional[str] = None
            match_sha: Optional[str] = None

            if etype not in {"PushEvent", "PullRequestEvent", "ReleaseEvent"}:
                continue

            if etype == "PushEvent":
                commits = payload.get("commits") or []
                if isinstance(commits, list):
                    for c in commits:
                        if not isinstance(c, dict):
                            continue
                        msg = c.get("message") or ""
                        if rx.search(msg):
                            match_text = _first_line(msg)
                            match_where = "commit_message"
                            match_sha = c.get("sha") or None
                            break

            elif etype == "PullRequestEvent":
                pr = payload.get("pull_request") or {}
                title = pr.get("title") or ""
                body = pr.get("body") or ""
                if rx.search(title):
                    match_text = _first_line(title)
                    match_where = "pr_title"
                elif rx.search(body):
                    match_text = "DeepSeek v4 mentioned in PR body"
                    match_where = "pr_body"

            elif etype == "ReleaseEvent":
                rel = payload.get("release") or {}
                name = rel.get("name") or ""
                tag = rel.get("tag_name") or ""
                body = rel.get("body") or ""
                if rx.search(name) or rx.search(tag):
                    match_text = _first_line(name or tag)
                    match_where = "release"
                elif rx.search(body):
                    match_text = "DeepSeek v4 mentioned in release notes"
                    match_where = "release_body"

            if not match_text:
                continue

            url = _best_event_url(repo, ev, match_sha)
            out.append(
                {
                    "provider": provider,
                    "kind": "github_v4_signal",
                    "source": "github_watch",
                    "source_id": f"{repo}:{ev_id}",
                    "title": f"{repo} {etype}: {match_text}",
                    "url": url,
                    "published_at": created_at,
                    "fetched_at": _now_iso(),
                    "payload": {
                        "repo": repo,
                        "event_id": ev_id,
                        "event_type": etype,
                        "actor": actor,
                        "created_at": created_at,
                        "match_where": match_where,
                        "match_text": match_text,
                        "commit_sha": match_sha,
                    },
                }
            )

    return out
