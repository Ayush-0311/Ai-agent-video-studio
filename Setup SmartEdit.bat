@echo off
setlocal
cd /d "%~dp0"

echo ========================================
echo SmartEdit AI - One Time Setup
echo ========================================
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python not found. Install Python 3.11+ or keep the existing Python available on PATH.
  pause
  exit /b 1
)

where npm >nul 2>nul
if errorlevel 1 (
  echo [ERROR] npm not found. Install Node.js LTS first.
  pause
  exit /b 1
)

if not exist "backend\.venv\Scripts\python.exe" (
  echo Creating backend Python virtual environment...
  python -m venv backend\.venv
  if errorlevel 1 (
    echo [ERROR] Failed to create backend virtual environment.
    pause
    exit /b 1
  )
) else (
  echo Backend virtual environment already exists.
)

echo Installing backend Python dependencies...
"backend\.venv\Scripts\python.exe" -m pip install -r backend\requirements.txt
if errorlevel 1 (
  echo [ERROR] Failed to install backend dependencies.
  pause
  exit /b 1
)

if not exist "node_modules" (
  echo Installing Electron dependencies...
  npm install
  if errorlevel 1 (
    echo [ERROR] Failed to install Electron dependencies.
    pause
    exit /b 1
  )
) else (
  echo Electron dependencies already exist.
)

echo.
echo ========================================
echo Setup complete.
echo Next time, double-click: Launch SmartEdit.bat
echo ========================================
pause
