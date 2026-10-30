<#
  PlainSight Windows launcher.

  What it does, in order:
    1. Checks the project folder and finds Python 3.10+.
    2. Checks for Ollama; downloads and installs it (per-user, no admin) if missing.
    3. Makes sure the Ollama server is running (starts it if not).
    4. Detects physical RAM and selects a suitable local Gemma 4 model (or validates a Gemma 4 override).
    5. Creates/reuses .venv and installs requirements.txt.
    6. Starts the app with MODEL set to the chosen model and opens the browser.

  Usage:
    .\START-PLAINSIGHT.cmd
    powershell -NoProfile -ExecutionPolicy Bypass -File .\start-plainsight.ps1 -Port 8001
    powershell -NoProfile -ExecutionPolicy Bypass -File .\start-plainsight.ps1 -Model gemma4:e4b
#>
[CmdletBinding()]
param(
    [string]$Model = '',
    [int]$Port = 8000,
    [string]$BindAddress = '127.0.0.1'
)

$ErrorActionPreference = 'Stop'
$ProjectDir = $PSScriptRoot
Set-Location -LiteralPath $ProjectDir

try {
    [Net.ServicePointManager]::SecurityProtocol =
        [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
} catch { }

$OllamaBase = 'http://127.0.0.1:11434'

function Write-Step([string]$Message) {
    Write-Host ''
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Stop-Launcher([string]$Message) {
    Write-Host ''
    Write-Host "ERROR: $Message" -ForegroundColor Red
    exit 1
}

function Test-Http([string]$Url) {
    try {
        $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
        return ($r.StatusCode -eq 200)
    } catch {
        return $false
    }
}

function Test-PortInUse([int]$P) {
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $iar = $client.BeginConnect('127.0.0.1', $P, $null, $null)
        if ($iar.AsyncWaitHandle.WaitOne(500) -and $client.Connected) { return $true }
        return $false
    } catch {
        return $false
    } finally {
        $client.Close()
    }
}

function Test-PythonOk {
    param([string]$Exe, [string[]]$PreArgs = @())
    $old = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $out = & $Exe @PreArgs -c "import sys; print(str(sys.version_info[0]) + '.' + str(sys.version_info[1]))" 2>$null
        if ($LASTEXITCODE -ne 0) { return $false }
        $text = $out | Select-Object -First 1
        if ($text -notmatch '^(\d+)\.(\d+)$') { return $false }
        $major = [int]$Matches[1]
        $minor = [int]$Matches[2]
        return ($major -gt 3 -or ($major -eq 3 -and $minor -ge 10))
    } catch {
        return $false
    } finally {
        $ErrorActionPreference = $old
    }
}

function Find-Python {
    $candidates = @(
        @{ Exe = 'py';      PreArgs = @('-3') },
        @{ Exe = 'python';  PreArgs = @() },
        @{ Exe = 'python3'; PreArgs = @() }
    )
    foreach ($c in $candidates) {
        if (Test-PythonOk -Exe $c.Exe -PreArgs $c.PreArgs) { return $c }
    }
    return $null
}

function Find-Ollama {
    $cmd = Get-Command ollama -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $known = @()
    if ($env:LOCALAPPDATA) { $known += (Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe') }
    if ($env:ProgramFiles) { $known += (Join-Path $env:ProgramFiles 'Ollama\ollama.exe') }
    foreach ($p in $known) {
        if (Test-Path -LiteralPath $p) { return $p }
    }
    return $null
}

function Install-Ollama {
    $installer = Join-Path $env:TEMP 'OllamaSetup.exe'
    $url = 'https://ollama.com/download/OllamaSetup.exe'

    Write-Host 'Downloading the Ollama installer (large file, this can take a while)...'
    $curl = Get-Command curl.exe -ErrorAction SilentlyContinue
    if ($curl) {
        & $curl.Source -L --fail -o $installer $url
        if ($LASTEXITCODE -ne 0) {
            Stop-Launcher 'Could not download Ollama. Check your internet connection, or install it manually from https://ollama.com/download and run this launcher again.'
        }
    } else {
        try {
            $ProgressPreference = 'SilentlyContinue'
            Invoke-WebRequest -Uri $url -OutFile $installer -UseBasicParsing
        } catch {
            Stop-Launcher 'Could not download Ollama. Check your internet connection, or install it manually from https://ollama.com/download and run this launcher again.'
        }
    }

    Write-Host 'Running the Ollama installer (per-user install, no administrator rights needed)...'
    $p = Start-Process -FilePath $installer -ArgumentList '/SILENT', '/NORESTART' -Wait -PassThru
    if ($p.ExitCode -ne 0) {
        Stop-Launcher "The Ollama installer exited with code $($p.ExitCode). Install Ollama manually from https://ollama.com/download and run this launcher again."
    }
    Remove-Item -LiteralPath $installer -Force -ErrorAction SilentlyContinue

    # Pick up the new PATH entry in this session.
    $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    $machinePath = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $env:Path = "$env:Path;$userPath;$machinePath"
}

Write-Host ''
Write-Host '=== PlainSight launcher ===' -ForegroundColor Green

# ---------------------------------------------------------------- 1. project + Python
Write-Step 'Checking the project folder'
foreach ($required in @('requirements.txt', 'app\main.py', 'static\index.html')) {
    if (-not (Test-Path -LiteralPath (Join-Path $ProjectDir $required))) {
        Stop-Launcher "Missing '$required'. Put START-PLAINSIGHT.cmd and start-plainsight.ps1 inside the plainsight project folder, next to requirements.txt."
    }
}
Write-Host "Project folder: $ProjectDir"

Write-Step 'Looking for Python 3.10 or newer'
$python = Find-Python
if (-not $python) {
    Stop-Launcher 'Python 3.10+ was not found. Install it from https://www.python.org/downloads/ (tick "Add python.exe to PATH"), then run this launcher again.'
}
Write-Host "Using Python via: $($python.Exe) $($python.PreArgs -join ' ')"

if (Test-PortInUse $Port) {
    Stop-Launcher "Port $Port is already in use. Close the other program or run with a different port, e.g.: powershell -NoProfile -ExecutionPolicy Bypass -File .\start-plainsight.ps1 -Port 8001"
}

# ---------------------------------------------------------------- 2. Ollama installed?
Write-Step 'Checking for Ollama'
$ollama = Find-Ollama
if ($ollama) {
    Write-Host "Ollama found: $ollama"
} else {
    Write-Host 'Ollama is not installed. Installing it now.'
    Install-Ollama
    $ollama = Find-Ollama
    if (-not $ollama) {
        Stop-Launcher 'Ollama was installed but ollama.exe could not be found. Close this window, open a new one, and run the launcher again.'
    }
    Write-Host "Ollama installed: $ollama"
}

# ---------------------------------------------------------------- 3. Ollama server running?
Write-Step 'Checking that the Ollama server is running'
if (Test-Http "$OllamaBase/api/tags") {
    Write-Host 'Ollama is already running; reusing it.'
} else {
    Write-Host 'Starting Ollama...'
    Start-Process -FilePath $ollama -ArgumentList 'serve' -WindowStyle Hidden | Out-Null
    $ready = $false
    for ($i = 0; $i -lt 60; $i++) {
        Start-Sleep -Seconds 1
        if (Test-Http "$OllamaBase/api/tags") { $ready = $true; break }
    }
    if (-not $ready) {
        Stop-Launcher 'The Ollama server did not start within 60 seconds. Open the Ollama app from the Start menu and run this launcher again.'
    }
    Write-Host 'Ollama is running.'
}

# ---------------------------------------------------------------- 4. Select and pull a Gemma model
if ([string]::IsNullOrWhiteSpace($Model)) {
    Write-Step 'Detecting system RAM and selecting a Gemma 4 model'
    $selector = Join-Path $ProjectDir 'scripts\select_model.py'
    $selection = & $python.Exe @($python.PreArgs) $selector
    if ($LASTEXITCODE -ne 0) {
        Stop-Launcher 'Could not detect system RAM. Choose a Gemma 4 model explicitly with -Model gemma4:e2b.'
    }
    Write-Host ($selection -join [Environment]::NewLine)
    $modelOnly = & $python.Exe @($python.PreArgs) $selector --model-only
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace(($modelOnly -join ''))) {
        Stop-Launcher 'Gemma model selection failed.'
    }
    $Model = ($modelOnly | Select-Object -Last 1).Trim()
} elseif ($Model -notmatch '^gemma(2|3|3n|4)?:[a-z0-9._-]+$' -or $Model -match 'cloud') {
    Stop-Launcher "Only local Gemma Ollama model tags are allowed. Examples: -Model gemma4:e4b, gemma3n:e4b, gemma3:12b"
}
Write-Step "Pulling Gemma model $Model (first time is a multi-GB download)"
& $ollama pull $Model
if ($LASTEXITCODE -ne 0) {
    Stop-Launcher "Could not pull '$Model'. Check your internet connection and free disk space. If the message above says a newer Ollama version is required, update Ollama from https://ollama.com/download and run this launcher again."
}

# ---------------------------------------------------------------- 5. venv + dependencies
Write-Step 'Preparing the Python environment (.venv)'
$venvPython = Join-Path $ProjectDir '.venv\Scripts\python.exe'
if (-not ((Test-Path -LiteralPath $venvPython) -and (Test-PythonOk -Exe $venvPython))) {
    Write-Host 'Creating virtual environment...'
    & $python.Exe @($python.PreArgs) -m venv --clear (Join-Path $ProjectDir '.venv')
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $venvPython)) {
        Stop-Launcher 'Could not create the virtual environment (.venv).'
    }
} else {
    Write-Host 'Reusing existing virtual environment.'
}

Write-Host 'Checking dependencies (pip)...'
& $venvPython -m pip install --disable-pip-version-check -r (Join-Path $ProjectDir 'requirements.txt')
if ($LASTEXITCODE -ne 0) {
    Stop-Launcher 'pip could not install the dependencies. Check your internet connection and try again.'
}

if (-not (Test-Path -LiteralPath (Join-Path $ProjectDir 'samples\bill.png'))) {
    Write-Host 'Generating sample documents...'
    & $venvPython (Join-Path $ProjectDir 'scripts\make_samples.py')
    if ($LASTEXITCODE -ne 0) {
        Write-Host 'Warning: could not generate sample images (the app will still work).' -ForegroundColor Yellow
    }
}

# ---------------------------------------------------------------- 6. Start the app
Write-Step "Starting PlainSight with model $Model"
$env:MODEL = $Model
$env:PYTHONUTF8 = '1'
$server = Start-Process -FilePath $venvPython `
    -ArgumentList @('-m', 'uvicorn', 'app.main:app', '--host', $BindAddress, '--port', "$Port") `
    -WorkingDirectory $ProjectDir -NoNewWindow -PassThru
$null = $server.Handle   # keep the handle so HasExited/ExitCode work reliably

try {
    $healthUrl = "http://127.0.0.1:$Port/api/health"
    $up = $false
    for ($i = 0; $i -lt 60; $i++) {
        if ($server.HasExited) { break }
        if (Test-Http $healthUrl) { $up = $true; break }
        Start-Sleep -Seconds 1
    }
    if (-not $up) {
        Stop-Launcher 'The app did not start. Look at the messages above for the reason.'
    }

    try {
        $health = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 5
        if (-not $health.ollama) {
            Write-Host 'Warning: the app cannot reach Ollama.' -ForegroundColor Yellow
        } elseif (-not $health.model) {
            Write-Host "Warning: Ollama does not list model '$Model'." -ForegroundColor Yellow
        }
    } catch { }

    $url = "http://localhost:$Port"
    Write-Host ''
    Write-Host "PlainSight is ready at $url" -ForegroundColor Green
    Start-Process $url
    Write-Host ''
    Write-Host 'Keep this window open. Press ENTER here to stop PlainSight (Ollama stays running).'
    [void](Read-Host)
} finally {
    if ($server -and -not $server.HasExited) {
        Write-Host 'Stopping PlainSight...'
        & taskkill.exe /PID $server.Id /T /F | Out-Null
    }
}
