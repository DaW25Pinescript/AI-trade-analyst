@echo off
:: ============================================================
::  AI Trade Analyst — Dashboard Launcher
::  Drop this file + generate_dashboard.py + dashboard_server.py
::  in your repo root. Double-click to launch.
::
::  The server recursively scans for *Progress*.md and *SPEC*.md
::  files, excluding .git, node_modules, __pycache__, etc.
:: ============================================================

title AI Trade Analyst Dashboard

:: Use the directory this .bat lives in as the working folder
cd /d "%~dp0"

echo.
echo  =============================================
echo   AI Trade Analyst — Dashboard Server
echo  =============================================
echo.

:: Check Python is available
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo  [ERROR] Python not found on your system.
    echo  Install Python 3 from https://python.org
    echo.
    pause
    exit /b 1
)

echo  Starting live dashboard server...
echo  Scanning for progress and spec files...
echo.

:: Start the server in the background, give it a moment to boot,
:: then open the browser
start /b python dashboard_server.py --folder . --port 9090

:: Wait for the server to start before opening Chrome
timeout /t 3 /nobreak >nul

:: Open the dashboard in the default browser
start "" "http://localhost:9090"

echo.
echo  Dashboard is running at http://localhost:9090
echo  Close this window to stop the server.
echo.

:: Keep the window alive so the background server keeps running
:: (Ctrl+C or closing the window will stop everything)
:loop
timeout /t 60 /nobreak >nul
goto loop
