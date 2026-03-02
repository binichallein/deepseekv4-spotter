from __future__ import annotations

import shutil
import subprocess
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass(frozen=True)
class Player:
    name: str
    argv_prefix: List[str]


def detect_player() -> Optional[Player]:
    """Pick an installed audio player capable of playing MP3."""

    # Order: common headless-friendly tools first.
    candidates: List[Player] = [
        Player("ffplay", ["ffplay", "-nodisp", "-autoexit", "-loglevel", "error"]),
        Player("mpv", ["mpv", "--no-video", "--really-quiet"]),
        Player("cvlc", ["cvlc", "--play-and-exit", "--quiet"]),
        Player("vlc", ["vlc", "--intf", "dummy", "--play-and-exit"]),
        Player("mpg123", ["mpg123", "-q"]),
        Player("afplay", ["afplay"]),
    ]

    for p in candidates:
        if shutil.which(p.argv_prefix[0]):
            return p
    return None


def play_mp3_loop(
    *,
    mp3_path: str,
    loops: int = 10,
    interval_seconds: int = 10,
    per_play_timeout_s: int = 600,
) -> Tuple[bool, str]:
    """Play mp3 `loops` times with `interval_seconds` between plays.

    Returns (ok, detail). If no player exists, returns (False, 'no_player').
    """

    mp3_path = (mp3_path or "").strip()
    if not mp3_path:
        return (False, "missing_mp3_path")

    player = detect_player()
    if not player:
        return (False, "no_player")

    loops = max(1, min(int(loops), 50))
    interval_seconds = max(0, min(int(interval_seconds), 3600))

    for i in range(loops):
        try:
            proc = subprocess.run(
                [*player.argv_prefix, mp3_path],
                capture_output=True,
                text=True,
                timeout=per_play_timeout_s,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return (False, f"timeout:{player.name}")
        except Exception as e:
            return (False, f"exception:{player.name}:{type(e).__name__}")

        if proc.returncode != 0:
            msg = (proc.stderr or proc.stdout or "").strip().splitlines()[:3]
            return (False, f"rc={proc.returncode}:{player.name}:{' | '.join(msg)}")

        if i != loops - 1 and interval_seconds:
            time.sleep(interval_seconds)

    return (True, player.name)
