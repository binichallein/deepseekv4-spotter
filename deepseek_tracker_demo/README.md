# DeepSeekV4 Spotter

DeepSeekV4 Spotter is a lightweight monitor that tries to detect DeepSeek v4 support signals as early as possible.

It watches two sources:
- Official DeepSeek website model label (`https://www.deepseek.com/`)
- GitHub repo events (Push / Pull Request / Release only), default repos:
  - `vllm-project/vllm`
  - `vllm-project/vllm-ascend`
  - `huggingface/transformers`

When a v4 signal is detected, it can:
- trigger a Feishu webhook
- play a local MP3 alarm in loops

## How Detection Works

The polling worker (`lite_poll.py`) runs two checks each round:

1. Official site model check
- Fetch homepage HTML
- Extract model token from `__NEXT_DATA__` (or fallback regex)
- If model changed from non-v4 to `v4` / `v4.*`, mark as v4 transition

2. GitHub signal check
- Query GitHub events API per repo: `/repos/{repo}/events`
- Only inspect event types:
  - `PushEvent` (commit message)
  - `PullRequestEvent` (PR title/body)
  - `ReleaseEvent` (release name/tag/body)
- Match regex (default): `deepseek\s*[-_]?\s*v4(\b|\.)`

Then trigger alert if either condition is true:
- official homepage transitions to v4
- a newly discovered GitHub v4 signal appears

## De-duplication Strategy

All events are stored in SQLite with unique key `(source, source_id)`.
- Repeated GitHub events are ignored automatically
- `ALERT_ONCE=1` makes v4 alert fire only once globally

## UI Design

The web UI is intentionally split into two layers:
- Monitor View (default): emotional "watch console" with just core status
- Detailed Panel (hidden by default): full config, poll snapshot, full event stream

## Quick Start

From repo root:

```bash
python -m deepseek_tracker_demo.lite_server \
  --interval-seconds 600 \
  --feishu-webhook-url "https://www.feishu.cn/flow/api/trigger-webhook/...." \
  --port 8000
```

Open:
- `http://127.0.0.1:8000/`

Manual one-shot poll:

```bash
python -m deepseek_tracker_demo.lite_poll
```

## Environment Variables

```bash
# Polling
export POLL_INTERVAL_SECONDS="600"   # default: 600, set 0 to disable auto polling

# Webhook
export FEISHU_WEBHOOK_URL="https://www.feishu.cn/flow/api/trigger-webhook/..."

# Audio alert
export ALERT_MP3_PATH="./闹钟 2-哔声_爱给网_aigei_com.mp3"
export ALERT_LOOPS="10"
export ALERT_INTERVAL_SECONDS="10"

# Fire alert only once for v4
export ALERT_ONCE="1"                # 1=true(default), 0=false

# GitHub watch repos
export WATCH_GITHUB_REPOS="vllm-project/vllm,vllm-project/vllm-ascend,huggingface/transformers"

# v4 match regex
export WATCH_DEEPSEEK_V4_REGEX="deepseek\\s*[-_]?\\s*v4(\\b|\\.)"

# Optional GitHub token (recommended for higher rate limits)
export GITHUB_TOKEN="ghp_..."
```

## API Endpoints

- `GET /` : web UI
- `GET /api/config` : runtime config used by monitor
- `GET /api/events?limit=80` : latest stored events
- `POST /api/poll` : run one polling round immediately

## Notes

- This is keyword-based early signal detection, not official confirmation.
- For best timeliness, reduce `POLL_INTERVAL_SECONDS` and configure `GITHUB_TOKEN`.
- If no audio player is installed (`mpg123`, `ffplay`, `mpv`, `vlc`, ...), audio step will fail but webhook can still work.
