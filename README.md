# DeepSeekV4 Spotter

DeepSeekV4 Spotter is a lightweight early-warning monitor for DeepSeek v4 related signals.

It watches:
- DeepSeek official homepage model label (`https://www.deepseek.com/`)
- GitHub repo events (only `PushEvent`, `PullRequestEvent`, `ReleaseEvent`) on:
`vllm-project/vllm`, `vllm-project/vllm-ascend`, `huggingface/transformers`

When a v4 signal appears, it can:
- trigger your webhook
- play alarm MP3 (looped, interval-based)

## Detection Logic

Each poll round (`lite_poll.py`) runs two checks:

1. Homepage check
- Fetch DeepSeek homepage HTML
- Parse model token (first from `__NEXT_DATA__`, then regex fallback)
- Detect transition from non-v4 to `v4`/`v4.*`

2. GitHub check
- Query `/repos/{repo}/events`
- Scan only:
`PushEvent` commit message, `PullRequestEvent` title/body, `ReleaseEvent` name/tag/body
- Match regex (default): `deepseek\\s*[-_]?\\s*v4(\\b|\\.)`

Alert is fired if:
- homepage transitions to v4, or
- new GitHub v4 signal event is found

## De-duplication

Events are stored in SQLite with unique key `(source, source_id)`.
- repeated GitHub events are ignored
- `ALERT_ONCE=1` (default) makes v4 alert fire only once globally

## UI Structure

- Main monitor view: simple “console” style status
- Detailed panel (hidden by default): config/event details + runtime settings

## Runtime Customization (No Hardcoded Secrets)

You can set webhook/audio at runtime in the Detailed Panel:
- Save/Clear webhook URL
- Upload custom mp3 and activate immediately
- Or set an absolute mp3 path manually
- Reset to default bundled music

Local runtime settings are saved to:
- `runtime_settings.json` (gitignored)
- uploaded files under `user_audio/` (gitignored)

So your private webhook URL will not be committed by default.

## Quick Start

From repo root:

```bash
chmod +x install.sh
bash install.sh
```

Then start service:

```bash
python lite_server.py \
  --interval-seconds 600 \
  --port 8000
```

Open:
- `http://127.0.0.1:8000/`

Then:
1. Click `Open Detailed Panel`
2. Set your webhook URL
3. Keep default music or upload your own mp3

Manual one-shot poll:

```bash
python lite_poll.py
```

## Environment Variables (Optional)

```bash
# Polling
export POLL_INTERVAL_SECONDS="600"   # default 600, set 0 to disable auto polling

# Webhook (can also be set from UI)
export FEISHU_WEBHOOK_URL="https://your-webhook-url"

# Audio alert (can also be set from UI)
export ALERT_MP3_PATH="./闹钟 2-哔声_爱给网_aigei_com.mp3"
export ALERT_LOOPS="10"
export ALERT_INTERVAL_SECONDS="10"

# Fire alert only once for v4
export ALERT_ONCE="1"                # 1=true(default), 0=false

# GitHub watch repos
export WATCH_GITHUB_REPOS="vllm-project/vllm,vllm-project/vllm-ascend,huggingface/transformers"

# v4 match regex
export WATCH_DEEPSEEK_V4_REGEX="deepseek\\s*[-_]?\\s*v4(\\b|\\.)"

# Optional token for higher GitHub API rate limits
export GITHUB_TOKEN="ghp_xxx"
```

## API Endpoints

- `GET /` : web UI
- `GET /api/config` : effective runtime config
- `GET /api/events?limit=80` : latest events
- `POST /api/poll` : run one poll immediately
- `POST /api/settings` : set/clear webhook or audio path
- `POST /api/upload_audio` : upload mp3 and activate as alert audio

`POST /api/settings` examples:

```json
{"webhook_url":"https://your-webhook-url"}
```

```json
{"webhook_url":""}
```

```json
{"alert_mp3_path":"/abs/path/custom.mp3"}
```

```json
{"alert_mp3_mode":"default"}
```

`POST /api/upload_audio` example:

```json
{"filename":"alarm.mp3","content_base64":"<base64>"}
```

## Notes

- This is early-signal detection, not official release confirmation.
- For faster detection, shorten poll interval and provide `GITHUB_TOKEN`.
- If no audio player is installed (`mpg123`, `ffplay`, `mpv`, `vlc`, ...), audio may fail while webhook still works.
