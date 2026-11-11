@echo off
chcp 65001 >nul
title LocalWhisper Pro v3.3
cd /d "%~dp0"
set PYTHONUNBUFFERED=1
set HF_HUB_DISABLE_SYMLINKS_WARNING=1

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" main.py %*
) else (
    echo [LocalWhisper] Virtual environment not found. Running install.bat first...
    call install.bat
    if %errorlevel% neq 0 (
        echo [LocalWhisper] Installation failed!
        pause
        exit /b 1
    )
    ".venv\Scripts\python.exe" main.py %*
)

if %errorlevel% neq 0 (
    echo.
    echo ===================================================
    echo [LocalWhisper] Application exited with error code %errorlevel%.
    echo Check the error logs above for details.
    echo ===================================================
    echo.
    pause
)
