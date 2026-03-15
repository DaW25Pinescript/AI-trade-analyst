@echo off
:: ============================================================
::  AI Trade Analyst — Fancy Dashboard Launcher
::  Double-click this to launch the beautiful live dashboard
:: ============================================================

title AI Trade Analyst Dashboard

:: Use the directory this .bat lives in as the working folder
cd /d "%~dp0"

echo.
echo  =============================================
echo   AI Trade Analyst — Fancy Dashboard Server
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

echo  Starting live fancy dashboard server...
echo  (Auto-detects docs folder + generate_dashboard.py)
echo.

:: Start the server (no --folder needed anymore)
start /b python dashboard_server.py --port 9090

:: Wait for the server to start
timeout /t 3 /nobreak >nul

:: Open the dashboard in the default browser
start "" "http://localhost:9090"

echo.
echo  Dashboard is running at http://localhost:9090
echo  Refresh the page = live update from your MD files
echo  Close this window to stop the server.
echo.

:: Keep the window alive
:loop
timeout /t 60 /nobreak >nul
goto loop