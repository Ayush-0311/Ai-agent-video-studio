@echo off
setlocal
cd /d "%~dp0"
title SmartEdit - Launch
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\desktop.ps1" -Action Launch
if errorlevel 1 (
    pause
    exit /b 1
)
exit /b 0
