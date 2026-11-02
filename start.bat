:: ============================================================
:: Start Agentic Workbench
:: Run from the agentic_workbench\ directory
:: ============================================================
@echo off
cd /d "%~dp0"

echo [1/3] Checking Python...
python --version
if errorlevel 1 (
    echo ERROR: Python not found on PATH.
    pause
    exit /b 1
)

echo [2/3] Checking .env...
if not exist ".env" (
    echo .env not found -- copying from .env.example
    copy .env.example .env
    echo Please edit .env and add your GITHUB_TOKEN, then re-run this script.
    notepad .env
    exit /b 1
)

echo [3/3] Launching Streamlit at http://localhost:8501 ...
python -m streamlit run app.py --server.port 8501 --server.headless false
