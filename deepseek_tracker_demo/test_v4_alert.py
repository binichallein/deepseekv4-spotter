from __future__ import annotations

import json
from datetime import datetime, timezone

from .audio_alert import play_mp3_loop
from .config import get_settings
from .db import connect, get_latest_homepage_model, init_db, insert_events
from .notify_feishu import send_feishu_webhook


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> None:
    s = get_settings()

    with connect(s.db_path) as conn:
        init_db(conn)
        prev = get_latest_homepage_model(conn, provider=s.provider)

    prev_model = (prev or {}).get("chosen") or "(unknown)"
    new_model = "v4"

    out = {
        "provider": s.provider,
        "prev_model": prev_model,
        "new_model": new_model,
        "feishu": None,
        "audio": None,
        "db_path": s.db_path,
    }

    # 1) Webhook
    if s.feishu_webhook_url:
        ok, detail = send_feishu_webhook(
            webhook_url=s.feishu_webhook_url,
            payload={
                "provider": s.provider,
                "signal": "test_v4_release",
                "prev_model": prev_model,
                "new_model": new_model,
                "url": s.homepage_url,
                "detected_at": _now_iso(),
                "test": True,
            },
        )
        out["feishu"] = {"attempted": True, "ok": ok, "detail": detail}

        audit_event = {
            "provider": s.provider,
            "kind": "test_webhook_sent" if ok else "test_webhook_failed",
            "source": "feishu",
            "source_id": f"test_v4:{_now_iso()}",
            "title": f"TEST Feishu webhook {'sent' if ok else 'failed'} for {prev_model} -> {new_model}",
            "url": s.feishu_webhook_url,
            "published_at": None,
            "fetched_at": _now_iso(),
            "payload": {"prev_model": prev_model, "new_model": new_model, "detail": detail, "test": True},
        }
        with connect(s.db_path) as conn:
            init_db(conn)
            insert_events(conn, [audit_event])
    else:
        out["feishu"] = {"attempted": False, "ok": None, "detail": "FEISHU_WEBHOOK_URL not set"}

    # 2) Audio
    if s.alert_mp3_path:
        ok, detail = play_mp3_loop(
            mp3_path=s.alert_mp3_path,
            loops=s.alert_loops,
            interval_seconds=s.alert_interval_seconds,
        )
        out["audio"] = {
            "attempted": True,
            "ok": ok,
            "detail": detail,
            "mp3": s.alert_mp3_path,
            "loops": s.alert_loops,
            "interval_seconds": s.alert_interval_seconds,
        }

        audit_event = {
            "provider": s.provider,
            "kind": "test_audio_played" if ok else "test_audio_failed",
            "source": "audio",
            "source_id": f"test_v4:{_now_iso()}",
            "title": f"TEST Audio alert {'played' if ok else 'failed'} for {new_model}",
            "url": s.alert_mp3_path,
            "published_at": None,
            "fetched_at": _now_iso(),
            "payload": {"new_model": new_model, "detail": detail, "test": True},
        }
        with connect(s.db_path) as conn:
            init_db(conn)
            insert_events(conn, [audit_event])
    else:
        out["audio"] = {"attempted": False, "ok": None, "detail": "ALERT_MP3_PATH not set"}

    print(json.dumps(out, ensure_ascii=True))


if __name__ == "__main__":
    main()
