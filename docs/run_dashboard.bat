@echo off
setlocal EnableExtensions

title AI Trade Analyst - Dashboard
cd /d "%~dp0"

set "PORT=9090"
set "BASE_DIR=%~dp0"
if "%BASE_DIR:~-1%"=="\" set "BASE_DIR=%BASE_DIR:~0,-1%"

set "DOCS_DIR="
if exist "%BASE_DIR%\docs\AI_TradeAnalyst_Progress.md" (
    set "DOCS_DIR=%BASE_DIR%\docs"
) else if exist "%BASE_DIR%\AI_TradeAnalyst_Progress.md" (
    set "DOCS_DIR=%BASE_DIR%"
)

set "SERVER_PY="
if exist "%BASE_DIR%\dashboard_server.py" (
    set "SERVER_PY=%BASE_DIR%\dashboard_server.py"
) else if exist "%BASE_DIR%\..\dashboard_server.py" (
    set "SERVER_PY=%BASE_DIR%\..\dashboard_server.py"
)

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python was not found in PATH.
    pause
    exit /b 1
)

if not defined DOCS_DIR (
    echo [ERROR] Could not find AI_TradeAnalyst_Progress.md.
    pause
    exit /b 1
)

if not defined SERVER_PY (
    echo [ERROR] Could not find dashboard_server.py.
    pause
    exit /b 1
)

start "AI Trade Analyst Server" cmd /k python "%SERVER_PY%" --port %PORT% --folder "%DOCS_DIR%"
timeout /t 3 /nobreak >nul
start "" "http://localhost:%PORT%"
exit /b 0
