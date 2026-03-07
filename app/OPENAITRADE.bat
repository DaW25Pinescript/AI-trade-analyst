@echo off
setlocal

set "APP_DIR=C:\Users\david\OneDrive\Documents\GitHub\ChartAnalysis\AI trade analyst\app"
set "PORT=8080"
set "PAGE=journey.html"

if not exist "%APP_DIR%\%PAGE%" (
    echo ERROR: Could not find "%APP_DIR%\%PAGE%"
    pause
    exit /b 1
)

cd /d "%APP_DIR%"

echo Starting local server from:
echo %APP_DIR%
echo.

where py >nul 2>nul
if %errorlevel%==0 (
    start "Journey Server" cmd /k py -m http.server %PORT%
) else (
    where python >nul 2>nul
    if %errorlevel%==0 (
        start "Journey Server" cmd /k python -m http.server %PORT%
    ) else (
        echo ERROR: Python was not found in PATH.
        echo Install Python or add it to PATH, then try again.
        pause
        exit /b 1
    )
)

timeout /t 2 /nobreak >nul
start "" "http://127.0.0.1:%PORT%/%PAGE%"

endlocal
