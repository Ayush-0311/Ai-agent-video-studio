@echo off
setlocal
cd /d "%~dp0"
title SmartEdit - First Time Setup
echo SmartEdit desktop setup - run again after project updates.
echo [1/5] Checking Python and Node.js...
python -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)" >nul 2>nul
if errorlevel 1 (
    echo ERROR: Install Python 3.11 or newer and enable Add Python to PATH.
    goto FAILED
)
where node >nul 2>nul
if errorlevel 1 (
    echo ERROR: Install Node.js LTS from https://nodejs.org/
    goto FAILED
)
where npm >nul 2>nul
if errorlevel 1 (
    echo ERROR: npm is missing. Repair your Node.js installation.
    goto FAILED
)
echo [2/5] Preparing the Python environment...
if not exist "backend\.venv\Scripts\python.exe" (
    python -m venv "backend\.venv"
    if errorlevel 1 goto FAILED
)
echo [3/5] Installing current backend requirements...
"backend\.venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto FAILED
"backend\.venv\Scripts\python.exe" -m pip install -r "backend\requirements.txt"
if errorlevel 1 goto FAILED
echo [4/5] Installing desktop dependencies...
call npm install --no-audit --no-fund
if errorlevel 1 goto FAILED
echo [5/5] Verifying backend, Electron, FFmpeg and FFprobe...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\desktop.ps1" -Action Check
if errorlevel 1 goto FAILED
echo.
echo SETUP COMPLETE - local desktop dependencies verified.
echo Next: upload colab\SmartEdit_Colab.ipynb to Google Colab and select T4 GPU.
echo Add NGROK_AUTHTOKEN in Colab Secrets and run all cells.
echo Wait for SMARTEDIT CONNECTION READY, then copy the ONE-PASTE CONNECTION LINK.
echo Double-click the 2. LAUNCH SmartEdit file and paste that link into the app.
echo Keep Colab running while generating images and voice.
pause
exit /b 0
:FAILED
echo.
echo SETUP FAILED - read the error above. Success has not been reported.
echo For missing FFmpeg or FFprobe, install the full FFmpeg package and add bin to PATH.
echo For dependency download errors, check Internet access and rerun this setup.
pause
exit /b 1
