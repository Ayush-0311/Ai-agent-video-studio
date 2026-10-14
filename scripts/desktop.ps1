param([ValidateSet('Launch', 'Backend', 'Stop', 'Check')][string]$Action = 'Launch')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$backendRoot = Join-Path $projectRoot 'backend'
$pythonExe = Join-Path $backendRoot '.venv\Scripts\python.exe'
$electronExe = Join-Path $projectRoot 'node_modules\electron\dist\electron.exe'
$logRoot = Join-Path $backendRoot 'studio-data\launcher'
Set-Location -LiteralPath $projectRoot

function Get-LocalBackend {
    try { return Invoke-RestMethod 'http://127.0.0.1:8000/api/studio/local-health' -TimeoutSec 3 }
    catch { return $null }
}
function Assert-OurBackend($health) {
    if ($health.app -ne 'SmartEdit AI' -or $health.backend_dir -ne $backendRoot) {
        throw 'Port 8000 belongs to another app or another SmartEdit folder. Close that app before launching this copy.'
    }
}
function Stop-VerifiedBackend($health) {
    Assert-OurBackend $health
    $backendProcessId = [int]$health.process_id
    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $backendProcessId"
    $commandLine = [string]$process.CommandLine
    if (!$process -or !$commandLine.Contains($backendRoot) -or $commandLine -notmatch 'uvicorn main:app') {
        throw 'Backend process identity could not be verified. No process was stopped.'
    }
    $jobs = Invoke-RestMethod 'http://127.0.0.1:8000/api/studio/jobs' -TimeoutSec 5
    if (@($jobs | Where-Object { $_.status -eq 'running' }).Count) {
        throw 'An export or generation is running. Wait for it to finish, then relaunch SmartEdit to update the backend.'
    }
    Stop-Process -Id $backendProcessId -Force -ErrorAction Stop
    Wait-Process -Id $backendProcessId -Timeout 10 -ErrorAction SilentlyContinue
}
function Get-CurrentBackend($health, $expectedFingerprint) {
    if (!$health) { return $null }
    Assert-OurBackend $health
    if ($health.runtime_fingerprint -eq $expectedFingerprint) { return $health }
    Write-Host 'Updating the background backend to match this editor...'
    Stop-VerifiedBackend $health
    return $null
}

$startupLock = New-Object System.Threading.Mutex($false, 'Local\SmartEditBackend8000')
$lockAcquired = $false
try {
    try { $lockAcquired = $startupLock.WaitOne(60000) }
    catch [System.Threading.AbandonedMutexException] { $lockAcquired = $true }
    if (!$lockAcquired) { throw 'Another SmartEdit launch is still starting the backend. Retry shortly.' }
    if ($Action -eq 'Stop') {
        $health = Get-LocalBackend
        if (!$health) { Write-Host 'No compatible SmartEdit backend found. No process was stopped.'; exit 0 }
        Stop-VerifiedBackend $health
        Write-Host 'SmartEdit backend stopped. Saved projects remain on disk.'
        exit 0
    }
    if (!(Test-Path -LiteralPath $pythonExe)) { throw 'Run the first-time SETUP file before launching.' }
    & $pythonExe (Join-Path $PSScriptRoot 'check_install.py')
    if ($LASTEXITCODE -ne 0) { throw 'Runtime check failed. See the error above; run SETUP after fixing missing prerequisites.' }
    if ($Action -eq 'Check') { exit 0 }
    $expectedFingerprint = (& $pythonExe (Join-Path $backendRoot 'runtime_version.py')).Trim()
    if ($LASTEXITCODE -ne 0 -or !$expectedFingerprint) { throw 'Could not read backend runtime version.' }
    $health = Get-CurrentBackend (Get-LocalBackend) $expectedFingerprint
    if (!$health) {
        $listener = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
        if ($listener) { throw 'Port 8000 is occupied by an older backend or another app. Close it and retry. No process was stopped.' }
        New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
        $arguments = '-m uvicorn main:app --host 127.0.0.1 --port 8000 --app-dir "' + $backendRoot + '"'
        $started = Start-Process -FilePath $pythonExe -ArgumentList $arguments -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru `
            -RedirectStandardOutput (Join-Path $logRoot 'backend-out.log') -RedirectStandardError (Join-Path $logRoot 'backend-error.log')
        $deadline = (Get-Date).AddSeconds(60)
        do {
            Start-Sleep -Milliseconds 500
            $health = Get-LocalBackend
            if ($health) { break }
            if ($started.HasExited) { throw "Backend exited during startup. Read $logRoot\backend-error.log" }
        } while ((Get-Date) -lt $deadline)
        if (!$health) { throw "Backend startup timed out. Read $logRoot\backend-error.log" }
    }
    Assert-OurBackend $health
    if ($health.runtime_fingerprint -ne $expectedFingerprint) { throw 'Backend version does not match this editor. Relaunch SmartEdit.' }
    Write-Host 'SmartEdit production backend is ready.'
    if ($Action -eq 'Backend') { exit 0 }
    Write-Host 'Colab: run colab\SmartEdit_Colab.ipynb on a GPU runtime.'
    Write-Host 'Wait for SMARTEDIT CONNECTION READY, then paste the ONE-PASTE CONNECTION LINK into the app.'
    # Electron is the user-requested visible app; only the backend runs hidden.
    Start-Process -FilePath $electronExe -ArgumentList ('"' + $projectRoot + '"') -WorkingDirectory $projectRoot | Out-Null
    Write-Host 'Desktop app opened. Use Stop SmartEdit Backend.bat after exports finish to stop the background backend.'
} catch {
    Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host $_.InvocationInfo.PositionMessage
    exit 1
} finally {
    if ($lockAcquired) { $startupLock.ReleaseMutex() }
    $startupLock.Dispose()
}
