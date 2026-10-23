param([switch]$SkipModels)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$runtimeRoot = Join-Path $projectRoot '.runtime'
$downloadRoot = Join-Path $runtimeRoot 'downloads'
$pythonExe = Join-Path $projectRoot 'backend\.venv\Scripts\python.exe'
Set-Location -LiteralPath $projectRoot
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

function Refresh-SetupPath {
    $env:PATH = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
        [Environment]::GetEnvironmentVariable('Path', 'User') + ';' + $env:PATH
}
function Install-Prerequisite([string]$package) {
    if (!(Get-Command winget.exe -ErrorAction SilentlyContinue)) {
        throw "Windows App Installer (winget) is missing. Install App Installer from Microsoft Store, then rerun SETUP. Required package: $package"
    }
    Write-Host "Installing $package using Windows Package Manager..."
    & winget.exe install --id $package --exact --source winget --silent --accept-package-agreements --accept-source-agreements --disable-interactivity
    if ($LASTEXITCODE -ne 0) { throw "Installation failed for $package (exit $LASTEXITCODE). Rerun SETUP after resolving the message above." }
    Refresh-SetupPath
}
function Find-Python {
    $candidates = @($pythonExe)
    $candidates += Join-Path $env:LOCALAPPDATA 'Programs\Python\Python311\python.exe'
    $command = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($command) { $candidates += $command.Source }
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            & $candidate -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)' 2>$null
            if ($LASTEXITCODE -eq 0) { return $candidate }
        }
    }
    return $null
}
function Ensure-FFmpeg {
    # A script path avoids Windows PowerShell 5.1 stripping quotes in python -c.
    $found = & $pythonExe (Join-Path $projectRoot 'backend\runtime_tools.py')
    if ($LASTEXITCODE -eq 0 -and $found) {
        $candidate = Get-Command $found.Trim() -ErrorAction SilentlyContinue
        if ($candidate) {
            $probe = Join-Path (Split-Path -Parent $candidate.Source) 'ffprobe.exe'
            if (Test-Path -LiteralPath $probe) {
                & $probe -version *> $null
                if ($LASTEXITCODE -eq 0) { Write-Host 'Reusing installed FFmpeg and FFprobe.'; return }
            }
        }
    }
    New-Item -ItemType Directory -Path $downloadRoot -Force | Out-Null
    $baseUrl = 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip'
    $checksum = (Invoke-WebRequest ($baseUrl + '.sha256') -UseBasicParsing).Content
    if ($checksum -is [byte[]]) { $checksum = [Text.Encoding]::UTF8.GetString($checksum) }
    $match = [regex]::Match([string]$checksum, '(?i)\b[0-9a-f]{64}\b')
    if (!$match.Success) { throw 'FFmpeg publisher did not return a valid SHA256 checksum.' }
    $expected = $match.Value
    $archive = Join-Path $downloadRoot 'ffmpeg.zip'
    $partial = Join-Path $downloadRoot 'ffmpeg.zip.partial'
    if (!(Test-Path -LiteralPath $archive) -or (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash -ne $expected) {
        if (!(Get-Command curl.exe -ErrorAction SilentlyContinue)) { throw 'Windows curl.exe is required for resumable FFmpeg download.' }
        $downloaded = $false
        for ($attempt = 1; $attempt -le 2; $attempt++) {
            Write-Host "Downloading FFmpeg + FFprobe (resume enabled), attempt $attempt..."
            & curl.exe --fail --location --retry 3 --connect-timeout 30 --continue-at - --output $partial $baseUrl
            $curlExit = $LASTEXITCODE
            if ((Test-Path -LiteralPath $partial) -and (Get-FileHash -LiteralPath $partial -Algorithm SHA256).Hash -eq $expected) {
                Move-Item -LiteralPath $partial -Destination $archive -Force
                $downloaded = $true
                break
            }
            if ($curlExit -ne 0 -and $curlExit -notin @(33, 22)) { throw 'FFmpeg download interrupted. Rerun SETUP to resume.' }
            # Only our failed download is discarded; installed tools remain intact.
            if (Test-Path -LiteralPath $partial) { Remove-Item -LiteralPath $partial }
        }
        if (!$downloaded) { throw 'FFmpeg checksum verification failed. No downloaded program was executed.' }
    }
    Expand-Archive -LiteralPath $archive -DestinationPath (Join-Path $runtimeRoot 'ffmpeg') -Force
}

$setupLock = New-Object System.Threading.Mutex($false, 'Local\SmartEditFirstTimeSetup')
$lockAcquired = $false
try {
    try { $lockAcquired = $setupLock.WaitOne(0) }
    catch [System.Threading.AbandonedMutexException] { $lockAcquired = $true }
    if (!$lockAcquired) { throw 'Another SmartEdit SETUP is already running.' }
    Write-Host '[1/6] Preparing Python and Node.js...'
    $bootstrapPython = Find-Python
    if (!$bootstrapPython) { Install-Prerequisite 'Python.Python.3.11'; $bootstrapPython = Find-Python }
    if (!$bootstrapPython) { throw 'Python was not found after installation. Reopen SETUP.' }
    if ((Test-Path -LiteralPath $pythonExe) -and $bootstrapPython -ne $pythonExe) {
        throw 'The existing backend\.venv is broken or uses Python older than 3.11. Rename that environment folder and rerun SETUP; projects and media are stored separately.'
    }
    if (!(Get-Command node.exe -ErrorAction SilentlyContinue) -or !(Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
        Install-Prerequisite 'OpenJS.NodeJS.LTS'
    }
    if (!(Get-Command npm.cmd -ErrorAction SilentlyContinue)) { throw 'Node.js/npm is unavailable. Reopen SETUP after installation.' }
    Write-Host '[2/6] Installing backend dependencies...'
    if (!(Test-Path -LiteralPath $pythonExe)) {
        & $bootstrapPython -m venv (Join-Path $projectRoot 'backend\.venv')
        if ($LASTEXITCODE -ne 0) { throw 'Could not create the Python environment.' }
    }
    & $pythonExe -m pip install --disable-pip-version-check -r (Join-Path $projectRoot 'backend\requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Backend dependency installation failed. Rerun SETUP to reuse downloaded packages.' }
    Write-Host '[3/6] Installing desktop dependencies...'
    & npm.cmd install --prefer-offline --no-audit --no-fund
    if ($LASTEXITCODE -ne 0) { throw 'Desktop dependency installation failed.' }
    Write-Host '[4/6] Preparing FFmpeg and FFprobe...'
    Ensure-FFmpeg
    Write-Host '[5/6] Preparing local speech model and fonts...'
    if (!$SkipModels) {
        & $pythonExe (Join-Path $PSScriptRoot 'prepare_local_models.py')
        if ($LASTEXITCODE -ne 0) { throw 'Local model preparation failed. Rerun SETUP to resume.' }
    }
    if (!(Test-Path -LiteralPath (Join-Path $env:WINDIR 'Fonts\Nirmala.ttf'))) {
        throw 'Nirmala UI font is missing. Restore Windows supplemental fonts for Hindi captions, then rerun SETUP.'
    }
    Write-Host '[6/6] Checking installed tools...'
    & $pythonExe (Join-Path $PSScriptRoot 'check_install.py')
    if ($LASTEXITCODE -ne 0) { throw 'Installation check failed.' }
    Write-Host 'SETUP COMPLETE. Local tools and selected models are ready.'
    Write-Host 'Next: upload colab/SmartEdit_Colab.ipynb, select GPU, and run its setup cell.'
    Write-Host 'Leave MOTION_ENGINE on auto for T4-compatible Wan. Optional LTX 13B needs A100-class GPU (38 GiB VRAM / 48 GiB RAM).'
    Write-Host 'Colab downloads its own selected planner, OmniVoice, image and motion weights.'
    Write-Host 'Paste its ONE-PASTE CONNECTION LINK into SmartEdit. Existing Colab sessions need the updated notebook.'
} catch {
    Write-Host "SETUP FAILED: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
} finally {
    if ($lockAcquired) { $setupLock.ReleaseMutex() }
    $setupLock.Dispose()
}
