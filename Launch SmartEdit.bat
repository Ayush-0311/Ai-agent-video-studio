@echo off
setlocal
cd /d "%~dp0"

echo ========================================
echo Starting SmartEdit AI Studio
echo ========================================
echo.

if not exist "backend\.venv\Scripts\python.exe" (
  echo [ERROR] Backend is not set up yet.
  echo Run "Setup SmartEdit.bat" first.
  pause
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "try { Invoke-RestMethod 'http://127.0.0.1:8000/' -TimeoutSec 1 | Out-Null; exit 0 } catch { exit 1 }" >nul 2>nul
if errorlevel 1 (
  echo Starting local FastAPI backend on http://127.0.0.1:8000 ...
  start "SmartEdit AI Backend" "%~dp0Start SmartEdit Backend.bat"
  echo Waiting for backend to become ready...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$ok=$false; for($i=0; $i -lt 45; $i++){ try { Invoke-RestMethod 'http://127.0.0.1:8000/' -TimeoutSec 1 | Out-Null; $ok=$true; break } catch { Start-Sleep -Seconds 1 } }; if(-not $ok){ exit 1 }"
  if errorlevel 1 (
    echo [ERROR] Backend did not start. Run "Start SmartEdit Backend.bat" to see the backend error.
    pause
    exit /b 1
  )
) else (
  echo Backend already running on http://127.0.0.1:8000
)

echo Launching Electron app...
npm start
