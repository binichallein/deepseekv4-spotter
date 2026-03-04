param(
    [switch]$NoSystem
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

function Write-Info([string]$Message) {
    Write-Host "[install-win] $Message"
}

function Test-Cmd([string]$Name) {
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Get-PythonInvocation() {
    if (Test-Cmd "py") { return @("py", "-3") }
    if (Test-Cmd "python") { return @("python") }
    return $null
}

function Invoke-ArrayCommand([string[]]$Cmd) {
    if ($Cmd.Count -le 0) { throw "empty_command" }
    if ($Cmd.Count -eq 1) { & $Cmd[0] }
    else { & $Cmd[0] @($Cmd[1..($Cmd.Count - 1)]) }
}

function Test-AudioPlayer() {
    foreach ($p in @("ffplay", "mpv", "vlc", "cvlc", "mpg123")) {
        if (Test-Cmd $p) { return $true }
    }
    return $false
}

$py = Get-PythonInvocation
if (-not $py -and -not $NoSystem -and (Test-Cmd "winget")) {
    Write-Info "Python not found. Installing Python 3.11 via winget..."
    winget install --id Python.Python.3.11 -e --source winget --accept-source-agreements --accept-package-agreements | Out-Null
    $py = Get-PythonInvocation
}

if (-not $py) {
    throw "Python 3 not found. Install Python 3.11+ first, then re-run install_windows.ps1"
}

if (-not $NoSystem -and -not (Test-AudioPlayer) -and (Test-Cmd "winget")) {
    Write-Info "Audio player not found. Installing FFmpeg (ffplay) via winget..."
    winget install --id Gyan.FFmpeg -e --source winget --accept-source-agreements --accept-package-agreements | Out-Null
}

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Info "Creating virtual environment in .venv"
    Invoke-ArrayCommand ($py + @("-m", "venv", ".venv"))
}

$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    throw ".venv\Scripts\python.exe not found after venv creation"
}

Write-Info "Installing Python dependencies"
$env:PIP_DISABLE_PIP_VERSION_CHECK = "1"
try {
    & $VenvPython -m pip install --upgrade pip setuptools wheel
}
catch {
    Write-Info "Retrying pip bootstrap with pypi.org"
    & $VenvPython -m pip install --upgrade pip setuptools wheel -i https://pypi.org/simple
}

try {
    & $VenvPython -m pip install -r requirements.txt
}
catch {
    Write-Info "Retrying requirements install with pypi.org"
    & $VenvPython -m pip install -r requirements.txt -i https://pypi.org/simple
}

if (-not (Test-Path "runtime_settings.json")) {
    Set-Content -Path "runtime_settings.json" -Value "{}" -Encoding Ascii
}

if (-not (Test-Path "user_audio")) {
    New-Item -ItemType Directory -Path "user_audio" | Out-Null
}

if (Test-AudioPlayer) {
    Write-Info "Audio player detected."
}
else {
    Write-Info "Warning: no audio player detected. Alert sound may fail."
}

Write-Host ""
Write-Host "[install-win] Done."
Write-Host ""
Write-Host "Start monitor:"
Write-Host "  .\.venv\Scripts\python.exe .\lite_server.py --host 0.0.0.0 --port 8000 --interval-seconds 600"
Write-Host ""
Write-Host "Open:"
Write-Host "  http://127.0.0.1:8000/"
