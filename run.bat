@echo off
chcp 65001 >nul
title LocalWhisper Pro v3.0
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" main.py %*
) else (
    echo [LocalWhisper] Virtual environment not found. Running install.bat first...
    call install.bat
    ".venv\Scripts\python.exe" main.py %*
)
