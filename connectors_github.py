from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _iso_or_none(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    # GitHub returns ISO 8601 like 2025-01-01T12:34:56Z
    return s.replace("Z", "+00:00")


_RE_REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def fetch_github_releases(
    *,
    repos: List[str],
    token: Optional[str],
    provider: str,
    timeout_s: float = 15.0,
) -> List[Dict[str, Any]]:
    """Fetch GitHub releases for a list of repos.

    Produces normalized event dicts for insertion.
    """

    events: List[Dict[str, Any]] = []

    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "deepseek-tracker-demo/0.1",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    sess = requests.Session()
    sess.headers.update(headers)

    for repo in repos:
        if not _RE_REPO.match(repo):
            continue

        url = f"https://api.github.com/repos/{repo}/releases"
        try:
            resp = sess.get(url, timeout=timeout_s)
            resp.raise_for_status()
            releases = resp.json()
        except Exception as e:
            events.append(
                {
                    "provider": provider,
                    "kind": "source_error",
                    "source": "github",
                    "source_id": f"error:{repo}",
                    "title": f"GitHub fetch failed for {repo}: {type(e).__name__}",
                    "url": url,
                    "published_at": None,
                    "fetched_at": _now_iso(),
                    "payload": {"repo": repo, "error": str(e)},
                }
            )
            continue

        if not isinstance(releases, list):
            continue

        for r in releases:
            rid = r.get("id")
            html_url = r.get("html_url")
            tag = r.get("tag_name")
            name = r.get("name")
            published_at = _iso_or_none(r.get("published_at"))

            title = f"{repo} release {tag or ''}".strip()
            if name:
                title = f"{repo}: {name} ({tag})" if tag else f"{repo}: {name}"

            if rid is None:
                continue

            events.append(
                {
                    "provider": provider,
                    "kind": "release",
                    "source": "github",
                    "source_id": str(rid),
                    "title": title,
                    "url": html_url,
                    "published_at": published_at,
                    "fetched_at": _now_iso(),
                    "payload": {
                        "repo": repo,
                        "tag_name": tag,
                        "draft": r.get("draft"),
                        "prerelease": r.get("prerelease"),
                        "tarball_url": r.get("tarball_url"),
                        "zipball_url": r.get("zipball_url"),
                    },
                }
            )

    return events
