param(
    [string]$ListenHost = "0.0.0.0",
    [int]$Port = 8000,
    [int]$IntervalSeconds = 600
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    throw ".venv\Scripts\python.exe not found. Run install_windows.ps1 first."
}

& $VenvPython ".\lite_server.py" --host $ListenHost --port $Port --interval-seconds $IntervalSeconds
