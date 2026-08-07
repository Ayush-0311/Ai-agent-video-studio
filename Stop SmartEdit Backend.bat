@echo off
setlocal

echo Stopping SmartEdit AI backend on port 8000...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$conns = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue; if($conns){ $conns | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { Stop-Process -Id $_ -Force; Write-Host ('Stopped process ' + $_) } } else { Write-Host 'No backend process found on port 8000.' }"
pause
