@echo off
REM Macro Context Reader -- dev environment launcher
REM Double-click to open PowerShell with venv activated

cd /d "%~dp0"

if not exist ".venv\Scripts\Activate.ps1" (
    echo [ERROR] Virtual environment not found at .venv\
    echo Run setup first: uv venv --python 3.11
    pause
    exit /b 1
)

powershell.exe -NoExit -ExecutionPolicy Bypass -Command "& {.\.venv\Scripts\Activate.ps1; Write-Host ''; Write-Host '=== Macro Context Reader dev environment ===' -ForegroundColor Cyan; Write-Host 'venv:' (python --version) -ForegroundColor Green; Write-Host 'cwd: ' (Get-Location) -ForegroundColor Green; Write-Host ''; Write-Host 'Quick commands:' -ForegroundColor Yellow; Write-Host '  pytest tests/ -v -m \"not integration\"' -ForegroundColor Gray; Write-Host '  pytest tests/ -v -m integration' -ForegroundColor Gray; Write-Host '  python -m macro_context_reader.market_pricing.real_rate_differential' -ForegroundColor Gray; Write-Host ''}"
