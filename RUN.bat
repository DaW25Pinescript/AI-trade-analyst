@echo off
setlocal EnableExtensions EnableDelayedExpansion

title AI Trade Analyst Bootstrap v6

cd /d "%~dp0"
set "ROOT=%CD%"

REM =====================================================
REM MODE SELECTION
REM =====================================================

set "MODE=react"

if "%1"=="legacy" (
    set "MODE=legacy"
)

echo ==============================================
echo AI Trade Analyst Bootstrap v6
echo Mode: %MODE%
echo Repo: %ROOT%
echo ==============================================
echo.

REM =====================================================
REM PATHS
REM =====================================================

set "VENV_PY=%ROOT%\.venv\Scripts\python.exe"

set "BACKEND_ENTRY=%ROOT%\ai_analyst\api\main.py"

set "REACT_UI_DIR=%ROOT%\ui"
set "REACT_UI_URL=http://localhost:5173"

set "LEGACY_APP_DIR=%ROOT%\app"
set "LEGACY_PAGE=journey.html"
set "LEGACY_UI_URL=http://127.0.0.1:8080/%LEGACY_PAGE%#/dashboard"

set "API_URL=http://127.0.0.1:8000"
set "API_HEALTH_URL=%API_URL%/health"
set "API_DOCS_URL=%API_URL%/docs"

set "PROXY_PORT=8317"
set "PROXY_URL=http://127.0.0.1:%PROXY_PORT%/management.html"

REM =====================================================
REM LOAD LOCAL ENV
REM =====================================================

if exist "%ROOT%\RUN.local.bat" (
    echo Loading RUN.local.bat...
    call "%ROOT%\RUN.local.bat"
)

REM =====================================================
REM SANITY CHECK
REM =====================================================

if not exist "%BACKEND_ENTRY%" (
    echo ERROR: Backend entrypoint missing.
    pause
    exit /b 1
)

REM =====================================================
REM ENSURE PYTHON VENV
REM =====================================================

call :ensure_venv
if errorlevel 1 goto :fail

REM =====================================================
REM ENSURE BACKEND DEPS
REM =====================================================

call :ensure_backend_deps
if errorlevel 1 goto :fail

REM =====================================================
REM START PROXY
REM =====================================================

call :ensure_proxy

REM =====================================================
REM START BACKEND
REM =====================================================

call :start_backend

echo Waiting for backend readiness...

call :wait_for_http_ok "%API_HEALTH_URL%" 20
if errorlevel 1 (
    echo WARNING: Backend health check failed.
) else (
    echo Backend ready.
)

REM =====================================================
REM START UI
REM =====================================================

if "%MODE%"=="legacy" (
    call :start_legacy_ui
) else (
    call :start_react_ui
)

REM =====================================================
REM SUMMARY
REM =====================================================

echo.
echo ==============================================
echo SYSTEM READY
echo ==============================================

if "%MODE%"=="legacy" (
    echo UI:      %LEGACY_UI_URL%
) else (
    echo UI:      %REACT_UI_URL%
)

echo Backend:  %API_DOCS_URL%
echo Proxy:    %PROXY_URL%

echo ==============================================
echo.

timeout /t 2 >nul

echo Opening browser tabs...

if "%MODE%"=="legacy" (
    start "" "%LEGACY_UI_URL%"
) else (
    start "" "%REACT_UI_URL%"
)

start "" "%API_DOCS_URL%"

call :port_in_use %PROXY_PORT%
if not errorlevel 1 start "" "%PROXY_URL%"

pause
exit /b 0


REM =====================================================
REM REACT UI START
REM =====================================================

:start_react_ui

echo Starting React UI...

where node >nul 2>nul
if errorlevel 1 (
    echo ERROR: Node.js not found in PATH.
    exit /b 1
)

if not exist "%REACT_UI_DIR%\package.json" (
    echo ERROR: /ui directory missing.
    exit /b 1
)

REM Install dependencies if needed
if not exist "%REACT_UI_DIR%\node_modules" (

    echo Installing UI dependencies...

    pushd "%REACT_UI_DIR%"
    call npm install
    if errorlevel 1 (
        echo ERROR: npm install failed.
        popd
        exit /b 1
    )
    popd

    echo UI dependencies installed.
)

call :port_in_use 5173
if not errorlevel 1 (
    echo React UI already running on port 5173.
    exit /b 0
)

start "AI Trade Analyst React UI" cmd /k "cd /d "%REACT_UI_DIR%" && npm run dev"

exit /b 0


REM =====================================================
REM LEGACY UI START
REM =====================================================

:start_legacy_ui

echo Starting legacy UI...

if not exist "%LEGACY_APP_DIR%\%LEGACY_PAGE%" (
    echo ERROR: Legacy UI files missing.
    exit /b 1
)

call :port_in_use 8080
if not errorlevel 1 (
    echo Legacy UI already running on 8080.
    exit /b 0
)

start "AI Trade Analyst Legacy UI" cmd /k "cd /d "%LEGACY_APP_DIR%" && "%VENV_PY%" -m http.server 8080 --bind 127.0.0.1"

exit /b 0


REM =====================================================
REM START BACKEND
REM =====================================================

:start_backend

call :port_in_use 8000
if not errorlevel 1 (
    echo Backend already running.
    exit /b 0
)

echo Starting backend...

start "AI Trade Analyst Backend" cmd /k "cd /d "%ROOT%" && "%VENV_PY%" -m uvicorn ai_analyst.api.main:app --reload --host 127.0.0.1 --port 8000"

exit /b 0


REM =====================================================
REM ENSURE VENV
REM =====================================================

:ensure_venv

if exist "%VENV_PY%" exit /b 0

echo Creating Python virtual environment...

py -m venv .venv

if not exist "%VENV_PY%" exit /b 1

exit /b 0


REM =====================================================
REM ENSURE BACKEND DEPENDENCIES
REM =====================================================

:ensure_backend_deps

"%VENV_PY%" -c "import fastapi,uvicorn,dotenv" >nul 2>nul
if not errorlevel 1 exit /b 0

echo Installing backend dependencies...

"%VENV_PY%" -m pip install fastapi "uvicorn[standard]" python-dotenv langgraph litellm python-multipart

exit /b 0


REM =====================================================
REM PROXY START
REM =====================================================

:ensure_proxy

call :port_in_use %PROXY_PORT%
if not errorlevel 1 (
    echo Proxy already running.
    exit /b 0
)

if exist "C:\cliproxyapi\cli-proxy-api.exe" (

    echo Starting CLIProxyAPI...

    start "CLIProxyAPI" cmd /k "cd /d C:\cliproxyapi && cli-proxy-api.exe"
)

exit /b 0


REM =====================================================
REM PORT CHECK
REM =====================================================

:port_in_use

netstat -ano | findstr /R /C:":%~1 .*LISTENING" >nul
exit /b %errorlevel%


REM =====================================================
REM WAIT FOR HTTP OK
REM =====================================================

:wait_for_http_ok

set "WAIT_URL=%~1"
set "WAIT_SECS=%~2"

set /a COUNT=0

:wait_loop

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
"try { $r = Invoke-WebRequest -UseBasicParsing -Uri '%WAIT_URL%' -TimeoutSec 2; if ($r.StatusCode -lt 400) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>nul

if not errorlevel 1 exit /b 0

if !COUNT! GEQ %WAIT_SECS% exit /b 1

set /a COUNT+=1
timeout /t 1 >nul

goto :wait_loop


REM =====================================================
REM FAILURE
REM =====================================================

:fail
echo.
echo Bootstrap failed.
pause
exit /b 1