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

function Test-CommandExists([string]$Exe) {
    if ([System.IO.Path]::IsPathRooted($Exe)) {
        return [bool](Test-Path $Exe)
    }
    return Test-Cmd $Exe
}

function Resolve-PythonCommand([string]$Exe, [string[]]$Args) {
    if (-not (Test-CommandExists $Exe)) {
        return $null
    }

    try {
        $out = (& $Exe @($Args + @("--version")) 2>&1 | Out-String).Trim()
        $exitCode = $LASTEXITCODE
    }
    catch {
        return $null
    }

    if ($exitCode -ne 0) {
        return $null
    }
    if ($out -match "Python was not found") {
        return $null
    }
    if ($out -notmatch "Python\s+\d+\.\d+") {
        return $null
    }

    return @{
        Exe = $Exe
        Args = $Args
    }
}

function Get-PythonCommand() {
    $cmd = Resolve-PythonCommand "py" @("-3")
    if ($cmd) {
        return $cmd
    }

    $cmd = Resolve-PythonCommand "python" @()
    if ($cmd) {
        return $cmd
    }

    # Fallback: common locations when PATH is stale right after installation.
    $candidates = @(
        (Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Python\Python311\python.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Python\Python310\python.exe"),
        (Join-Path $env:ProgramFiles "Python312\python.exe"),
        (Join-Path $env:ProgramFiles "Python311\python.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "Python311\python.exe")
    )
    foreach ($p in $candidates) {
        if (-not $p) { continue }
        $cmd = Resolve-PythonCommand $p @()
        if ($cmd) {
            return $cmd
        }
    }

    return $null
}

function Test-AudioPlayer() {
    foreach ($p in @("ffplay", "mpv", "vlc", "cvlc", "mpg123")) {
        if (Test-Cmd $p) { return $true }
    }
    return $false
}

$py = Get-PythonCommand
if (-not $py -and -not $NoSystem -and (Test-Cmd "winget")) {
    Write-Info "Python not found. Installing Python 3.11 via winget..."
    winget install --id Python.Python.3.11 -e --source winget --accept-source-agreements --accept-package-agreements | Out-Null
    $py = Get-PythonCommand
}

if (-not $py) {
    throw "Python 3 not found or not runnable (Microsoft Store alias may be active). Install Python 3.11+ and re-open PowerShell, then re-run install_windows.ps1."
}

if (-not $NoSystem -and -not (Test-AudioPlayer) -and (Test-Cmd "winget")) {
    Write-Info "Audio player not found. Installing FFmpeg (ffplay) via winget..."
    winget install --id Gyan.FFmpeg -e --source winget --accept-source-agreements --accept-package-agreements | Out-Null
}

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Info "Creating virtual environment in .venv"
    & $py.Exe @($py.Args + @("-m", "venv", ".venv"))
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
