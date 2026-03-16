@echo off
setlocal EnableExtensions
title AI Trade Analyst - Dashboard Server

cd /d "%~dp0"

echo =============================================
echo  AI Trade Analyst - Dashboard Server
echo =============================================

:: 1. Check if Python is installed [cite: 3]
where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python was not found in PATH. [cite: 3]
    pause
    exit /b 1
)

set "PORT=9090"
set "BASE_DIR=%~dp0"
if "%BASE_DIR:~-1%"=="\" set "BASE_DIR=%BASE_DIR:~0,-1%"

:: 2. Detect docs folder [cite: 4]
set "DOCS_DIR="
if exist "%BASE_DIR%\docs\AI_TradeAnalyst_Progress.md" (
    set "DOCS_DIR=%BASE_DIR%\docs"
) else if exist "%BASE_DIR%\AI_TradeAnalyst_Progress.md" (
    set "DOCS_DIR=%BASE_DIR%"
)

:: 3. Detect server script [cite: 4]
set "SERVER_PY="
if exist "%BASE_DIR%\dashboard_server_fixed.py" (
    set "SERVER_PY=%BASE_DIR%\dashboard_server_fixed.py"
) else if exist "%BASE_DIR%\..\dashboard_server_fixed.py" (
    set "SERVER_PY=%BASE_DIR%\..\dashboard_server_fixed.py"
) else if exist "%BASE_DIR%\dashboard_server.py" (
    set "SERVER_PY=%BASE_DIR%\dashboard_server.py"
)

:: 4. Validation
if not defined DOCS_DIR (
    echo [ERROR] Could not find AI_TradeAnalyst_Progress.md. [cite: 5]
    pause
    exit /b 1
)
if not defined SERVER_PY (
    echo [ERROR] Could not find dashboard_server.py script.
    pause
    exit /b 1
)

echo [INFO] Using docs folder: %DOCS_DIR%
echo [INFO] Server script: %SERVER_PY%
echo [INFO] Starting server on port %PORT%...

:: 5. Launch Server in a new window 
:: Use 'cmd /k' so the window stays open if Python crashes.
start "AI Trade Analyst Server" cmd /k python "%SERVER_PY%" --port %PORT% --folder "%DOCS_DIR%"

:: 6. Wait for server to initialize
echo [INFO] Waiting for server to start...
timeout /t 3 /nobreak >nul

:: 7. Open the browser
echo [INFO] Opening browser at http://localhost:%PORT%
start "" "http://localhost:%PORT%"

echo [INFO] Dashboard process complete. You can close this window.
pause
exit /b 0