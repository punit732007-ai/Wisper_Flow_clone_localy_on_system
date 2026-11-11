@echo off
title LocalWhisper Pro v3.3 — One-Click Setup
cd /d "%~dp0"
set HF_HUB_DISABLE_SYMLINKS_WARNING=1

echo ===================================================
echo   LocalWhisper Pro v3.3 — Installation & Setup
echo ===================================================
echo.

:: Check if uv is available, attempt auto-install if missing
where uv >nul 2>nul
if %errorlevel% neq 0 (
    echo [Info] uv package manager not found. Checking for Python...
    where python >nul 2>nul
    if %errorlevel% neq 0 (
        echo [Info] Neither uv nor python found. Installing ultra-fast uv via PowerShell...
        powershell -ExecutionPolicy ByPass -NoProfile -Command "irm https://astral.sh/uv/install.ps1 | iex"
        set "PATH=%USERPROFILE%\.local\bin;%PATH%"
    )
)

:: Re-check uv
where uv >nul 2>nul
if %errorlevel% equ 0 (
    echo [1/3] Setting up Python 3.11 virtual environment with uv...
    uv venv --python 3.11 .venv
    echo [2/3] Installing dependencies with high-speed uv...
    uv pip install -r requirements.txt --python .venv
) else (
    echo [1/3] Setting up Python virtual environment with standard python...
    python -m venv .venv
    echo [2/3] Installing dependencies with pip...
    .venv\Scripts\python.exe -m pip install --upgrade pip
    .venv\Scripts\python.exe -m pip install -r requirements.txt
)

if not exist ".venv\Scripts\python.exe" (
    echo.
    echo [ERROR] Virtual environment creation failed!
    echo Please ensure Python 3.11 or uv is installed on your system.
    pause
    exit /b 1
)

echo [3/3] Registering universal 'localwhisper' command & creating runners...
.venv\Scripts\python.exe register_command.py

echo.
echo ===================================================
echo   Installation Complete!
echo   Run by typing 'localwhisper' anywhere or run.bat
echo   Or double-click 'run_silent.vbs' for silent background mode!
echo ===================================================
echo.
pause
