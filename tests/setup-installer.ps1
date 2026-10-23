# Read-only native Windows PowerShell check: never install or download packages.
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $projectRoot 'backend\.venv\Scripts\python.exe'
$source = Get-Content -LiteralPath (Join-Path $projectRoot 'scripts/setup.ps1') -Raw
$start = $source.IndexOf('function Refresh-SetupPath')
$end = $source.IndexOf('$setupLock =')
. ([scriptblock]::Create($source.Substring($start, $end-$start)))
function Install-Prerequisite { throw 'Unexpected installation during read-only check' }
function Invoke-WebRequest { throw 'Unexpected FFmpeg download: existing installation was not discovered' }
if ((Find-Python) -ne $pythonExe) { throw 'The working virtual environment was not reused' }
Ensure-FFmpeg
$tokens = $null; $errors = $null
[System.Management.Automation.Language.Parser]::ParseInput($source, [ref]$tokens, [ref]$errors) | Out-Null
if ($errors.Count) { throw $errors[0].Message }
Write-Host 'Setup parser, Python reuse and native FFmpeg discovery: PASS'
