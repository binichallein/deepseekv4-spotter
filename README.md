<p align="center">
  <img src="./logo.png" alt="DeepSeekV4 Spotter Logo" width="240" />
</p>

# DeepSeekV4 Spotter

English version: [README_EN.md](./README_EN.md)

## 项目简介
DeepSeekV4 Spotter 是一个面向 DeepSeek v4 的早期信号监控器。

监控来源：
- DeepSeek 官网对话框模型标识（`https://www.deepseek.com/`）
- GitHub 仓库事件（仅 `PushEvent`、`PullRequestEvent`、`ReleaseEvent`）：
`vllm-project/vllm`、`vllm-project/vllm-ascend`、`huggingface/transformers`

触发条件：
- 官网模型从非 v4 变为 `v4/v4.*`
- GitHub 事件中出现 DeepSeek v4 关键词匹配

触发动作：
- 调用你自定义的 webhook
- 播放告警音乐（默认 `default_music.mp3`）

## 一键安装
在仓库根目录执行：

```bash
chmod +x install.sh
bash install.sh
```

只安装 Python 环境与依赖（不安装系统包）：

```bash
bash install.sh --no-system
```

## Windows 安装与启动（原生，不走 WSL）

在 PowerShell 中进入项目目录后执行：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\install_windows.ps1
```

启动方式（二选一）：

```powershell
.\start_windows.ps1
```

或双击：

```bat
start_windows.bat
```

## 启动服务

```bash
python lite_server.py --host 0.0.0.0 --port 8000 --interval-seconds 600
```

打开：
- `http://127.0.0.1:8000/`

## Web UI
- 主界面：情绪化监控器视图（简洁展示）
- 详细面板：可设置 webhook、上传自定义 mp3、查看配置与事件流

运行时配置文件（默认不入库）：
- `runtime_settings.json`
- `user_audio/`

## 常用环境变量

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
