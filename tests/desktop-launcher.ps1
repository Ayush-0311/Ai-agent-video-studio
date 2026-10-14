# Exercise production restart decisions with fake processes: never stop a real app.
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$backendRoot = Join-Path $projectRoot 'backend'
$source = Get-Content -Raw (Join-Path $projectRoot 'scripts/desktop.ps1')
$first = $source.IndexOf('function Get-LocalBackend')
$last = $source.IndexOf('$startupLock =')
. ([scriptblock]::Create($source.Substring($first, $last - $first)))
$script:stopped = @()
$script:jobs = @()
$script:command = 'python -m uvicorn main:app --app-dir "' + $backendRoot + '"'
function Get-CimInstance { param($Filter, $ClassName) return @{CommandLine=$script:command} }
function Invoke-RestMethod { param($Uri, $TimeoutSec) return $script:jobs }
function Stop-Process { param($Id, [switch]$Force, $ErrorAction) $script:stopped += $Id }
function Wait-Process { param($Id, $Timeout, $ErrorAction) }
function Check($ok, $message) { if (!$ok) { throw $message } }
function Reject($health, $message) {
    $script:stopped=@(); $rejected=$false
    try { Get-CurrentBackend $health 'new' | Out-Null } catch { $rejected=$true }
    Check ($rejected -and !$script:stopped.Count) $message
}
$legacy = @{app='SmartEdit AI'; backend_dir=$backendRoot; process_id=42}
$result = Get-CurrentBackend $legacy 'new'
Check (!$result -and $script:stopped.Count -eq 1 -and $script:stopped[0] -eq 42) 'Legacy backend was not replaced'
$script:stopped=@()
$current=$legacy.Clone(); $current.runtime_fingerprint='new'
$result=Get-CurrentBackend $current 'new'
Check ($result -and !$script:stopped.Count) 'Current backend was unnecessarily stopped'
$old=$legacy.Clone(); $old.runtime_fingerprint='old'
$result=Get-CurrentBackend $old 'new'
Check (!$result -and $script:stopped.Count -eq 1) 'Source changes did not trigger replacement'
$script:jobs=@(@{status='running'})
Reject $old 'Active generation/export was interrupted'
$script:jobs=@()
$other=$legacy.Clone(); $other.backend_dir='C:\another-app'
Reject $other 'Another app was stopped'
$script:command='python unrelated_server.py'
Reject $old 'Unverified process was stopped'
Check ($null -eq (Get-CurrentBackend $null 'new')) 'Offline backend should start normally'
Write-Host '7 launcher regression checks passed.'
