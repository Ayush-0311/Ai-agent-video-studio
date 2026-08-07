@echo off
setlocal
cd /d "%~dp0backend"

if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] Backend venv missing. Run "Setup SmartEdit.bat" first.
  pause
  exit /b 1
)

echo SmartEdit AI backend starting at http://127.0.0.1:8000
".venv\Scripts\python.exe" -m uvicorn main:app --host 127.0.0.1 --port 8000
pause
