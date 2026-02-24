@echo off
setlocal EnableExtensions

REM Always run from the BAT file folder (repo root)
cd /d "%~dp0"

set PORT=8000

echo ==========================================
echo AI Trade Analyst - Local Launcher
echo Folder: %CD%
echo Port: %PORT%
echo ==========================================
echo.

REM Check Python launcher first
where py >nul 2>nul
if %errorlevel%==0 goto :run_py

REM Check python.exe
where python >nul 2>nul
if %errorlevel%==0 goto :run_python

echo [ERROR] Python not found (py or python).
echo Install Python from python.org and tick "Add Python to PATH"
echo OR use the Node.js version of this launcher.
echo.
pause
goto :eof

:run_py
echo [OK] Found py launcher
echo Opening browser at http://localhost:%PORT%/app/
start "" "http://localhost:%PORT%/app/"
echo Starting server... (Press Ctrl+C to stop)
py -m http.server %PORT%
echo.
echo Server stopped or failed to start.
pause
goto :eof

:run_python
echo [OK] Found python
echo Opening browser at http://localhost:%PORT%/app/
start "" "http://localhost:%PORT%/app/"
echo Starting server... (Press Ctrl+C to stop)
python -m http.server %PORT%
echo.
echo Server stopped or failed to start.
pause
goto :eof