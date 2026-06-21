@echo off
:: ─────────────────────────────────────────────────────────────────
:: LocalWhisper — Quick Launcher
:: Activates the venv and runs the app from the project directory.
:: ─────────────────────────────────────────────────────────────────
call "%~dp0venv\Scripts\activate.bat"
python "%~dp0main.py" %*
