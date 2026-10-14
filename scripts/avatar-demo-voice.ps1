$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$demoRoot = Join-Path $projectRoot 'backend\studio-data\verification\avatar-demo'
New-Item -ItemType Directory -Path $demoRoot -Force | Out-Null
Add-Type -AssemblyName System.Speech
$narrator = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $narrator.Rate = 0
    $narrator.SetOutputToWaveFile((Join-Path $demoRoot 'speech-1.wav'))
    $narrator.Speak('Solar panels turn sunlight into electricity. Their cells capture energy from the sun.')
    $narrator.SetOutputToWaveFile((Join-Path $demoRoot 'speech-2.wav'))
    $narrator.Speak('An inverter makes this power usable at home. Batteries can store extra energy for later.')
    $narrator.SetOutputToNull()
} finally { $narrator.Dispose() }
Write-Host 'Two local demo narration files created.'
