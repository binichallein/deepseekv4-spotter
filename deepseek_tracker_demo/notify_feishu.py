from __future__ import annotations

import json
import shutil
import subprocess
import urllib.request
from typing import Any, Dict, Optional, Tuple


def send_feishu_webhook(
    *,
    webhook_url: str,
    payload: Dict[str, Any],
    timeout_s: float = 8.0,
) -> Tuple[bool, str]:
    """Send a JSON payload to a Feishu webhook.

    Preference: use curl (as requested), fallback to urllib if curl isn't available.
    Returns (ok, detail).
    """

    webhook_url = (webhook_url or "").strip()
    if not webhook_url:
        return (False, "missing_webhook_url")

    data = json.dumps(payload, ensure_ascii=True).encode("utf-8")

    curl = shutil.which("curl")
    if curl:
        try:
            proc = subprocess.run(
                [
                    curl,
                    "-sS",
                    "-X",
                    "POST",
                    "-H",
                    "Content-Type: application/json",
                    "--max-time",
                    str(int(timeout_s)),
                    "-d",
                    data.decode("utf-8"),
                    webhook_url,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if proc.returncode == 0:
                return (True, (proc.stdout or "").strip()[:400])
            return (False, (proc.stderr or proc.stdout or "curl_failed").strip()[:400])
        except Exception as e:
            return (False, f"curl_exception:{type(e).__name__}")

    # Fallback: stdlib HTTP
    try:
        req = urllib.request.Request(
            webhook_url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            body = resp.read(400)
        return (True, body.decode("utf-8", errors="replace"))
    except Exception as e:
        return (False, f"urllib_exception:{type(e).__name__}")
