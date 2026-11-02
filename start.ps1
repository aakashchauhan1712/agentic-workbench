# ============================================================
# Start Agentic Workbench (PowerShell)
# Run from: agentic_workbench\
# ============================================================

$ErrorActionPreference = "Stop"

Write-Host "[1/4] Checking Python..." -ForegroundColor Cyan
python --version

Write-Host "[2/4] Verifying .env..." -ForegroundColor Cyan
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from template. Please add your GITHUB_TOKEN." -ForegroundColor Yellow
    notepad .env
    exit 1
}

Write-Host "[3/4] Checking Copilot runtime..." -ForegroundColor Cyan
python -m copilot download-runtime 2>&1 | Out-Null
Write-Host "  Runtime ready." -ForegroundColor Green

Write-Host "[4/4] Starting Streamlit app at http://localhost:8501" -ForegroundColor Green
python -m streamlit run app.py --server.port 8501 --server.headless false
