@echo off
title LocalWhisper Pro — One-Click Setup
cd /d "%~dp0"

echo ===================================================
echo   LocalWhisper Pro v3.0 — Installation & Setup
echo ===================================================
echo.

:: Check if uv is available
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

echo [3/3] Registering universal 'localwhisper' command...
.venv\Scripts\python.exe register_command.py

echo.
echo ===================================================
echo   Installation Complete!
echo   Run by typing 'localwhisper' anywhere or run.bat
echo ===================================================
echo.
pause
