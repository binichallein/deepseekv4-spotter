#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

NO_SYSTEM=0

for arg in "$@"; do
  case "$arg" in
    --no-system)
      NO_SYSTEM=1
      ;;
    -h|--help)
      cat <<'EOF'
Usage: bash install.sh [--no-system]

Options:
  --no-system   Skip system package installation and only set up Python venv.
  -h, --help    Show this help.
EOF
      exit 0
      ;;
    *)
      echo "[install] Unknown argument: $arg" >&2
      exit 1
      ;;
  esac
done

log() {
  echo "[install] $*"
}

pip_run() {
  .venv/bin/python -m pip "$@"
}

pip_install_with_fallback() {
  local args=("$@")
  if pip_run "${args[@]}"; then
    return 0
  fi

  log "Pip install failed with current index, retrying via https://pypi.org/simple"
  pip_run "${args[@]}" -i https://pypi.org/simple
}

have_cmd() {
  command -v "$1" >/dev/null 2>&1
}

has_audio_player() {
  local p
  for p in ffplay mpv cvlc vlc mpg123 afplay; do
    if have_cmd "$p"; then
      return 0
    fi
  done
  return 1
}

detect_python() {
  if have_cmd python3; then
    echo "python3"
    return 0
  fi
  if have_cmd python; then
    echo "python"
    return 0
  fi
  return 1
}

detect_pkg_manager() {
  if have_cmd apt-get; then
    echo "apt"
    return 0
  fi
  if have_cmd dnf; then
    echo "dnf"
    return 0
  fi
  if have_cmd yum; then
    echo "yum"
    return 0
  fi
  if have_cmd pacman; then
    echo "pacman"
    return 0
  fi
  if have_cmd brew; then
    echo "brew"
    return 0
  fi
  return 1
}

SUDO=""
if [[ "${EUID:-$(id -u)}" -ne 0 ]] && have_cmd sudo; then
  SUDO="sudo"
fi

SYSTEM_NEED=0
if ! detect_python >/dev/null; then
  SYSTEM_NEED=1
fi
if ! has_audio_player; then
  SYSTEM_NEED=1
fi
if ! have_cmd curl; then
  SYSTEM_NEED=1
fi

if [[ "$NO_SYSTEM" -eq 1 ]]; then
  log "--no-system enabled, skip system package installation."
elif [[ "$SYSTEM_NEED" -eq 1 ]]; then
  if PKG="$(detect_pkg_manager)"; then
    log "Installing system packages via: $PKG"
    case "$PKG" in
      apt)
        $SUDO apt-get update -y
        $SUDO apt-get install -y python3 python3-pip python3-venv curl mpg123
        ;;
      dnf)
        $SUDO dnf install -y python3 python3-pip curl mpg123 || $SUDO dnf install -y python3 python3-pip curl ffmpeg
        ;;
      yum)
        $SUDO yum install -y python3 python3-pip curl mpg123 || $SUDO yum install -y python3 python3-pip curl ffmpeg
        ;;
      pacman)
        $SUDO pacman -Sy --noconfirm python python-pip curl mpg123
        ;;
      brew)
        brew install python curl mpg123
        ;;
    esac
  else
    log "No supported package manager found. Please install Python 3 + pip + an audio player manually."
  fi
else
  log "System dependencies already look good."
fi

PYTHON_BIN="$(detect_python || true)"
if [[ -z "$PYTHON_BIN" ]]; then
  echo "[install] Python is required but was not found after installation." >&2
  exit 1
fi

log "Using Python: $PYTHON_BIN"

if [[ ! -d ".venv" ]]; then
  log "Creating virtual environment in .venv"
  "$PYTHON_BIN" -m venv .venv
fi

if [[ ! -x ".venv/bin/python" ]]; then
  echo "[install] .venv appears broken; remove it and re-run install.sh" >&2
  exit 1
fi

log "Installing Python dependencies"
export PIP_DISABLE_PIP_VERSION_CHECK=1
pip_install_with_fallback install --upgrade pip setuptools wheel
pip_install_with_fallback install -r requirements.txt

if [[ ! -f runtime_settings.json ]]; then
  printf '{}\n' > runtime_settings.json
fi
mkdir -p user_audio

if has_audio_player; then
  log "Audio player found."
else
  log "Warning: no audio player detected. Alert sound may fail."
fi

cat <<'EOF'

[install] Done.

Start monitor:
  ./.venv/bin/python lite_server.py --host 0.0.0.0 --port 8000 --interval-seconds 600

Open:
  http://127.0.0.1:8000/
EOF
