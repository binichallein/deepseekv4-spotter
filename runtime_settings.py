from __future__ import annotations

import os
import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, Iterable


SETTINGS_PATH = os.path.join(os.path.dirname(__file__), "runtime_settings.json")
AUDIO_DIR = os.path.join(os.path.dirname(__file__), "user_audio")


def load_runtime_settings() -> Dict[str, Any]:
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
        return {}
    except FileNotFoundError:
        return {}
    except Exception:
        return {}


def _atomic_write(path: str, content: str) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(content)
    os.replace(tmp, path)


def save_runtime_settings(settings: Dict[str, Any]) -> None:
    data = settings if isinstance(settings, dict) else {}
    _atomic_write(SETTINGS_PATH, json.dumps(data, ensure_ascii=True, sort_keys=True, indent=2))


def update_runtime_settings(*, set_values: Dict[str, Any] | None = None, clear_keys: Iterable[str] | None = None) -> Dict[str, Any]:
    data = load_runtime_settings()

    if set_values:
        for k, v in set_values.items():
            data[str(k)] = v

    if clear_keys:
        for k in clear_keys:
            data.pop(str(k), None)

    save_runtime_settings(data)
    return data


def _safe_name(name: str) -> str:
    base = os.path.basename((name or "").strip()) or "custom.mp3"
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", base)
    if not base.lower().endswith(".mp3"):
        base += ".mp3"
    return base


def save_uploaded_mp3(*, filename: str, content: bytes) -> str:
    os.makedirs(AUDIO_DIR, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_name = f"{ts}_{_safe_name(filename)}"
    out_path = os.path.abspath(os.path.join(AUDIO_DIR, out_name))
    with open(out_path, "wb") as f:
        f.write(content)
    return out_path
