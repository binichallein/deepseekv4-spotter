@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo [start-win] .venv\Scripts\python.exe not found.
  echo [start-win] Please run install_windows.ps1 first.
  pause
  exit /b 1
)

".venv\Scripts\python.exe" "lite_server.py" --host 0.0.0.0 --port 8000 --interval-seconds 600
