@echo off
setlocal
cd /d "%~dp0"
echo Finish or cancel active exports before stopping the backend.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\desktop.ps1" -Action Stop
if errorlevel 1 (
    pause
    exit /b 1
)
pause
exit /b 0
