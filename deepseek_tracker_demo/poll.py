from __future__ import annotations

import argparse
from typing import Any, Dict, List

from .config import get_settings
from .connectors_deepseek_docs import fetch_deepseek_docs_news
from .connectors_deepseek_homepage import fetch_deepseek_homepage_model
from .connectors_github import fetch_github_releases
from .connectors_rss import fetch_rss
from .db import connect, init_db, insert_events


def run_poll() -> Dict[str, Any]:
    s = get_settings()

    gathered: List[Dict[str, Any]] = []

    gathered.extend(
        fetch_deepseek_homepage_model(
            homepage_url=s.homepage_url,
            provider=s.provider,
        )
    )

    if s.docs_news_seed_urls:
        gathered.extend(
            fetch_deepseek_docs_news(
                seed_urls=s.docs_news_seed_urls,
                provider=s.provider,
                cookie=s.docs_cookie,
                fetch_limit=s.docs_fetch_limit,
            )
        )

    if s.github_repos:
        gathered.extend(
            fetch_github_releases(
                repos=s.github_repos,
                token=s.github_token,
                provider=s.provider,
            )
        )

    if s.rss_feeds:
        gathered.extend(fetch_rss(feeds=s.rss_feeds, provider=s.provider))

    with connect(s.db_path) as conn:
        init_db(conn)
        inserted = insert_events(conn, gathered)

    return {
        "provider": s.provider,
        "db_path": s.db_path,
        "sources": {
            "homepage_url": s.homepage_url,
            "docs_news_seed_urls": s.docs_news_seed_urls,
            "github_repos": s.github_repos,
            "rss_feeds": s.rss_feeds,
        },
        "fetched": len(gathered),
        "inserted": inserted,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", help="Run a single poll")
    args = ap.parse_args()

    if args.once:
        res = run_poll()
        print(res)
        return

    ap.error("Only --once is supported in this demo. Use: python -m deepseek_tracker_demo.poll --once")


if __name__ == "__main__":
    main()
