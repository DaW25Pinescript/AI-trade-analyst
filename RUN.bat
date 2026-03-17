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
REM PREREQUISITE CHECK (fresh machine safety net)
REM =====================================================

call :check_prerequisites
if errorlevel 1 goto :fail

REM =====================================================
REM FIRST-RUN SETUP (API key + local config)
REM =====================================================

call :ensure_local_config

REM =====================================================
REM LOAD LOCAL ENV
REM =====================================================

if exist "%ROOT%\RUN.local.bat" (
    echo Loading RUN.local.bat...
    call "%ROOT%\RUN.local.bat"
)

REM =====================================================
REM PROPAGATE API KEY TO FRONTEND
REM =====================================================

call :ensure_frontend_env

REM =====================================================
REM SANITY CHECK
REM =====================================================

if not exist "%BACKEND_ENTRY%" (
    echo ERROR: Backend entrypoint missing: %BACKEND_ENTRY%
    echo        Did you clone the full repository?
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
REM ENSURE FRONTEND DEPS
REM =====================================================

call :ensure_frontend_deps
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
REM PREREQUISITE CHECK
REM
REM Uses goto-based flow instead of nested if/else blocks
REM to avoid cmd.exe parenthesis parsing bugs in echo text.
REM =====================================================

:check_prerequisites

set "PREREQ_FAIL=0"

echo Checking prerequisites...

REM --- Resolve Python launcher ---

set "PY_CMD="

py --version >nul 2>nul
if not errorlevel 1 set "PY_CMD=py"

if "!PY_CMD!"=="" (
    python --version >nul 2>nul
    if not errorlevel 1 set "PY_CMD=python"
)

if "!PY_CMD!"=="" goto :prereq_python_missing
for /f "tokens=*" %%v in ('!PY_CMD! --version 2^>nul') do echo   Python:  %%v [launcher: !PY_CMD!]
goto :prereq_python_done

:prereq_python_missing
echo.
echo   [MISSING] Python is not installed or not in PATH.
echo.
echo   How to install:
echo     1. Go to https://www.python.org/downloads/
echo     2. Download Python 3.11 or later
echo     3. IMPORTANT: Check "Add Python to PATH" during install
echo     4. Restart this script after installing
echo.
set "PREREQ_FAIL=1"

:prereq_python_done

REM --- Node.js ---

where node >nul 2>nul
if errorlevel 1 goto :prereq_node_missing
for /f "tokens=*" %%v in ('node --version 2^>nul') do echo   Node.js: %%v
goto :prereq_node_done

:prereq_node_missing
echo.
echo   [MISSING] Node.js is not installed or not in PATH.
echo.
echo   How to install:
echo     1. Go to https://nodejs.org/
echo     2. Download the LTS version (20.x or later)
echo     3. Run the installer with default settings
echo     4. Restart this script after installing
echo.
set "PREREQ_FAIL=1"

:prereq_node_done

REM --- npm ---

where npm >nul 2>nul
if errorlevel 1 goto :prereq_npm_missing
for /f "tokens=*" %%v in ('npm --version 2^>nul') do echo   npm:     v%%v
goto :prereq_npm_done

:prereq_npm_missing
echo.
echo   [MISSING] npm is not available. It should come with Node.js.
echo             Try reinstalling Node.js from https://nodejs.org/
echo.
set "PREREQ_FAIL=1"

:prereq_npm_done

REM --- Git (optional) ---

where git >nul 2>nul
if errorlevel 1 goto :prereq_git_missing
for /f "tokens=*" %%v in ('git --version 2^>nul') do echo   Git:     %%v
goto :prereq_git_done

:prereq_git_missing
echo   Git:     not found - optional, install from https://git-scm.com/

:prereq_git_done

REM --- PowerShell execution policy ---

powershell -NoProfile -Command "if ((Get-ExecutionPolicy -Scope CurrentUser) -eq 'Restricted') { exit 1 } else { exit 0 }" >nul 2>nul
if not errorlevel 1 goto :prereq_policy_done

echo.
echo   [WARNING] PowerShell execution policy is Restricted.
echo             npm scripts may fail. Fixing automatically...
echo.

powershell -NoProfile -Command "Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned -Force" >nul 2>nul
if errorlevel 1 goto :prereq_policy_manual

echo   Execution policy set to RemoteSigned.
goto :prereq_policy_done

:prereq_policy_manual
echo   Could not set execution policy automatically.
echo   Run this in PowerShell manually:
echo     Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
echo.

:prereq_policy_done

REM --- CLIProxyAPI ---

if exist "C:\cliproxyapi\cli-proxy-api.exe" (
    echo   Proxy:   CLIProxyAPI found
) else (
    echo   Proxy:   CLIProxyAPI not found at C:\cliproxyapi\
    echo            LLM requests will fail without a proxy. See project README.
)

echo.

if "!PREREQ_FAIL!"=="1" (
    echo ==============================================
    echo PREREQUISITES MISSING - cannot continue.
    echo Install the items marked [MISSING] above,
    echo then run this script again.
    echo ==============================================
    echo.
    exit /b 1
)

echo Prerequisites OK.
echo.

exit /b 0


REM =====================================================
REM FIRST-RUN SETUP
REM =====================================================

:ensure_local_config

if exist "%ROOT%\RUN.local.bat" exit /b 0

echo.
echo ==============================================
echo FIRST-RUN SETUP
echo ==============================================
echo.
echo No local configuration found. Let's set it up.
echo.
echo This system uses CLIProxyAPI to route LLM requests
echo through a local proxy.
echo.
echo You need the client token from your CLIProxyAPI setup.
echo.
echo Where to find it:
echo   1. Open CLIProxyAPI management page
echo      http://127.0.0.1:8317/management.html
echo   2. Look for the client API key / token
echo   3. Enter it below
echo.
echo This single key is used for:
echo   - Authenticating LLM requests through the proxy
echo   - Securing the backend /analyse API endpoint
echo   - Authenticating the frontend UI to the backend
echo.
echo The key is stored locally in RUN.local.bat and is git-ignored.
echo You can change it later by editing that file.
echo.
echo NOTE: Use a simple alphanumeric token. Avoid special
echo       characters like ^& ^| ^%% ^^ ^!
echo.

set /p "USER_KEY=Enter your CLIProxyAPI client token: "

if "%USER_KEY%"=="" (
    echo.
    echo No key entered. You can create RUN.local.bat manually later.
    echo The system will start but API authentication will fail.
    echo.
    exit /b 0
)

echo.
echo Creating RUN.local.bat...

(
    echo @echo off
    echo REM Local, untracked overrides for AI Trade Analyst bootstrap.
    echo REM Keep this file out of git. Do not commit real secrets.
    echo REM Generated by first-run setup on %DATE% %TIME%
    echo.
    echo REM CLIProxyAPI client token - used for LLM proxy auth:
    echo set "LOCAL_LLM_PROXY_API_KEY=%USER_KEY%"
    echo.
    echo REM Backend API authentication - same key secures /analyse endpoint:
    echo set "AI_ANALYST_API_KEY=%USER_KEY%"
    echo.
    echo REM LLM proxy base URL:
    echo set "CLAUDE_PROXY_BASE_URL=http://127.0.0.1:%PROXY_PORT%/v1"
) > "%ROOT%\RUN.local.bat"

echo.
echo Configuration saved to RUN.local.bat
echo You can edit this file anytime to change your key or proxy URL.
echo.
echo ==============================================
echo.

exit /b 0


REM =====================================================
REM REACT UI START
REM =====================================================

:start_react_ui

echo Starting React UI...

if not exist "%REACT_UI_DIR%\package.json" (
    echo ERROR: /ui directory missing.
    exit /b 1
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

!PY_CMD! -m venv .venv

if not exist "%VENV_PY%" (
    echo ERROR: Failed to create virtual environment.
    echo        Python launcher: !PY_CMD!
    echo        Check that Python is installed correctly.
    exit /b 1
)

echo Virtual environment created.

exit /b 0


REM =====================================================
REM ENSURE BACKEND DEPENDENCIES
REM =====================================================

:ensure_backend_deps

"%VENV_PY%" -c "import fastapi,uvicorn,pandas,apscheduler" >nul 2>nul
if not errorlevel 1 exit /b 0

echo Installing backend dependencies...

"%VENV_PY%" -m pip install -e ".[dev,mdo]"

if errorlevel 1 (
    echo ERROR: Backend dependency installation failed.
    exit /b 1
)

echo Backend dependencies installed.

exit /b 0


REM =====================================================
REM ENSURE FRONTEND DEPENDENCIES
REM =====================================================

:ensure_frontend_deps

if not exist "%REACT_UI_DIR%\package.json" exit /b 0

REM If node_modules is populated, skip
if exist "%REACT_UI_DIR%\node_modules\.package-lock.json" exit /b 0

echo Installing frontend dependencies...

pushd "%REACT_UI_DIR%"

REM Use npm ci for reproducible installs when lockfile exists
if exist "package-lock.json" (
    call npm ci
) else (
    call npm install
)

if errorlevel 1 (
    echo ERROR: npm install failed.
    popd
    exit /b 1
)

popd

echo Frontend dependencies installed.

exit /b 0


REM =====================================================
REM ENSURE FRONTEND ENV (API KEY PROPAGATION)
REM =====================================================

:ensure_frontend_env

if "%AI_ANALYST_API_KEY%"=="" (
    echo WARNING: AI_ANALYST_API_KEY not set. Frontend auth will fail.
    echo          Run this script again or edit RUN.local.bat to add your key.
    exit /b 0
)

set "ENV_FILE=%REACT_UI_DIR%\.env.local"

REM Check if file already has the correct value
if exist "%ENV_FILE%" (
    findstr /C:"VITE_API_KEY=%AI_ANALYST_API_KEY%" "%ENV_FILE%" >nul 2>nul
    if not errorlevel 1 exit /b 0
)

echo Propagating API key to frontend...
echo VITE_API_KEY=%AI_ANALYST_API_KEY%> "%ENV_FILE%"
echo Frontend env updated: ui\.env.local

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

if not exist "C:\cliproxyapi\cli-proxy-api.exe" exit /b 0

echo Starting CLIProxyAPI...

start "CLIProxyAPI" cmd /k "cd /d C:\cliproxyapi && cli-proxy-api.exe"

echo Waiting for proxy readiness...
call :wait_for_http_ok "http://127.0.0.1:%PROXY_PORT%/management.html" 10
if errorlevel 1 (
    echo WARNING: Proxy health check timed out. LLM requests may fail.
) else (
    echo Proxy ready.
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
echo Bootstrap failed. See errors above.
pause
exit /b 1
