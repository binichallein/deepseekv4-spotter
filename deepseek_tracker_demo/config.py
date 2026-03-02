from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List

from .runtime_settings import load_runtime_settings


@dataclass(frozen=True)
class Settings:
    db_path: str
    provider: str
    homepage_url: str
    poll_interval_seconds: int
    feishu_webhook_url: str | None
    alert_mp3_path: str | None
    alert_loops: int
    alert_interval_seconds: int
    alert_once: bool
    watch_github_repos: List[str]
    watch_deepseek_v4_regex: str
    docs_news_seed_urls: List[str]
    docs_cookie: str | None
    docs_fetch_limit: int
    github_repos: List[str]
    rss_feeds: List[str]
    github_token: str | None


def _csv_env(name: str) -> List[str]:
    v = (os.getenv(name) or "").strip()
    if not v:
        return []
    return [x.strip() for x in v.split(",") if x.strip()]


def get_settings() -> Settings:
    # Keep defaults conservative and user-editable.
    # You can override with env vars:
    # - TRACKER_DB_PATH
    # - PROVIDER (default: deepseek)
    # - DEEPSEEK_GITHUB_REPOS (comma-separated: owner/repo)
    # - DEEPSEEK_RSS_FEEDS (comma-separated)
    # - GITHUB_TOKEN

    db_path = os.getenv("TRACKER_DB_PATH") or os.path.join(
        os.path.dirname(__file__), "data.sqlite3"
    )

    provider = os.getenv("PROVIDER") or "deepseek"

    homepage_url = (os.getenv("DEEPSEEK_HOMEPAGE_URL") or "").strip() or "https://www.deepseek.com/"

    try:
        poll_interval_seconds = int(os.getenv("POLL_INTERVAL_SECONDS") or "600")
    except ValueError:
        poll_interval_seconds = 600
    # 0 disables auto polling.
    if poll_interval_seconds != 0 and poll_interval_seconds < 10:
        poll_interval_seconds = 10

    feishu_webhook_url = (os.getenv("FEISHU_WEBHOOK_URL") or "").strip() or None

    default_mp3 = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "闹钟 2-哔声_爱给网_aigei_com.mp3")
    )
    if not os.path.exists(default_mp3):
        default_mp3 = ""

    alert_mp3_path = (os.getenv("ALERT_MP3_PATH") or "").strip() or default_mp3 or None
    try:
        alert_loops = int(os.getenv("ALERT_LOOPS") or "10")
    except ValueError:
        alert_loops = 10
    if alert_loops < 1:
        alert_loops = 1
    if alert_loops > 50:
        alert_loops = 50

    try:
        alert_interval_seconds = int(os.getenv("ALERT_INTERVAL_SECONDS") or "10")
    except ValueError:
        alert_interval_seconds = 10
    if alert_interval_seconds < 0:
        alert_interval_seconds = 0
    if alert_interval_seconds > 3600:
        alert_interval_seconds = 3600

    alert_once = (os.getenv("ALERT_ONCE") or "1").strip().lower() not in {"0", "false", "no", "off"}

    watch_github_repos = _csv_env("WATCH_GITHUB_REPOS")
    if not watch_github_repos:
        watch_github_repos = [
            "vllm-project/vllm",
            "vllm-project/vllm-ascend",
            "huggingface/transformers",
        ]

    # Default: require \"deepseek\" and \"v4\" to appear close, to reduce false positives.
    watch_deepseek_v4_regex = (os.getenv("WATCH_DEEPSEEK_V4_REGEX") or "").strip() or (
        r"deepseek\s*[-_]?\s*v4(\b|\.)"
    )

    # Seed pages used to discover the news list (sidebar nav links).
    # If the docs site becomes gated, set DEEPSEEK_DOCS_COOKIE.
    docs_news_seed_urls = _csv_env("DEEPSEEK_DOCS_NEWS_SEEDS")
    if not docs_news_seed_urls:
        docs_news_seed_urls = [
            "https://api-docs.deepseek.com/zh-cn/news/news251201",
        ]
    docs_cookie = (os.getenv("DEEPSEEK_DOCS_COOKIE") or "").strip() or None
    try:
        docs_fetch_limit = int(os.getenv("DEEPSEEK_DOCS_NEWS_FETCH_LIMIT") or "0")
    except ValueError:
        docs_fetch_limit = 0
    if docs_fetch_limit < 0:
        docs_fetch_limit = 0
    if docs_fetch_limit > 50:
        docs_fetch_limit = 50

    # NOTE: Repo names may change. Treat this as a starting point.
    github_repos = _csv_env("DEEPSEEK_GITHUB_REPOS")
    if not github_repos:
        github_repos = [
            "deepseek-ai/DeepSeek-V3",
            "deepseek-ai/DeepSeek-R1",
        ]

    rss_feeds = _csv_env("DEEPSEEK_RSS_FEEDS")

    github_token = (os.getenv("GITHUB_TOKEN") or "").strip() or None

    # Runtime overrides set by the web UI.
    runtime = load_runtime_settings()
    if "feishu_webhook_url" in runtime:
        feishu_webhook_url = (str(runtime.get("feishu_webhook_url") or "")).strip() or None
    if "alert_mp3_path" in runtime:
        v = (str(runtime.get("alert_mp3_path") or "")).strip()
        alert_mp3_path = v or default_mp3 or None

    return Settings(
        db_path=db_path,
        provider=provider,
        homepage_url=homepage_url,
        poll_interval_seconds=poll_interval_seconds,
        feishu_webhook_url=feishu_webhook_url,
        alert_mp3_path=alert_mp3_path,
        alert_loops=alert_loops,
        alert_interval_seconds=alert_interval_seconds,
        alert_once=alert_once,
        watch_github_repos=watch_github_repos,
        watch_deepseek_v4_regex=watch_deepseek_v4_regex,
        docs_news_seed_urls=docs_news_seed_urls,
        docs_cookie=docs_cookie,
        docs_fetch_limit=docs_fetch_limit,
        github_repos=github_repos,
        rss_feeds=rss_feeds,
        github_token=github_token,
    )
