<p align="center">
  <img src="./logo.png" alt="DeepSeekV4 Spotter Logo" width="240" />
</p>

# DeepSeekV4 Spotter

中文版本: [README.md](./README.md)

## Overview
DeepSeekV4 Spotter is an early-signal monitor for DeepSeek v4.

Sources:
- DeepSeek homepage model label (`https://www.deepseek.com/`)
- GitHub repo events (only `PushEvent`, `PullRequestEvent`, `ReleaseEvent`) from:
`vllm-project/vllm`, `vllm-project/vllm-ascend`, `huggingface/transformers`

Triggers:
- Homepage model transitions from non-v4 to `v4/v4.*`
- New GitHub event matches DeepSeek v4 keyword pattern

Actions:
- Send your custom webhook
- Play alert music (default: `default_music.mp3`)

## One-click Install
Run in repo root:

```bash
chmod +x install.sh
bash install.sh
```

Install only Python venv/deps (skip system packages):

```bash
bash install.sh --no-system
```

## Windows Native Setup (No WSL)

From PowerShell in repo root:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\install_windows.ps1
```

Start server (choose one):

```powershell
.\start_windows.ps1
```

or double-click:

```bat
start_windows.bat
```

## Start

```bash
python lite_server.py --host 0.0.0.0 --port 8000 --interval-seconds 600
```

Open:
- `http://127.0.0.1:8000/`

## Web UI
- Main monitor view: simplified emotional console
- Detailed panel: configure webhook, upload custom mp3, inspect config/events

Runtime local files (ignored by git):
- `runtime_settings.json`
- `user_audio/`

## Common Environment Variables

```bash
export POLL_INTERVAL_SECONDS="600"
export FEISHU_WEBHOOK_URL="https://your-webhook-url"
export ALERT_MP3_PATH="./default_music.mp3"
export ALERT_LOOPS="10"
export ALERT_INTERVAL_SECONDS="10"
export ALERT_ONCE="1"
export WATCH_GITHUB_REPOS="vllm-project/vllm,vllm-project/vllm-ascend,huggingface/transformers"
export WATCH_DEEPSEEK_V4_REGEX="deepseek\\s*[-_]?\\s*v4(\\b|\\.)"
export GITHUB_TOKEN="ghp_xxx"
```

## API
- `GET /`
- `GET /api/config`
- `GET /api/events?limit=80`
- `POST /api/poll`
- `POST /api/settings`
- `POST /api/upload_audio`
