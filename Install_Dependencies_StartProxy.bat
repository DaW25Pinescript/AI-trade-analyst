@echo off
setlocal EnableExtensions EnableDelayedExpansion

title AI Trade Analyst Bootstrap v3

REM =========================================================
REM Repo-root bootstrap v3:
REM - creates/uses .venv
REM - checks/install backend deps (including python-multipart)
REM - checks/starts CLIProxyAPI first from its own folder
REM - waits for proxy confirmation on 8317
REM - starts backend on 8000 and waits for /health
REM - starts UI static server on 8080
REM - opens browser pages
REM Put this .bat in the repo root and double-click it.
REM =========================================================

cd /d "%~dp0"
set "ROOT=%CD%"
set "VENV_PY=%ROOT%\.venv\Scripts\python.exe"
set "APP_DIR=%ROOT%\app"
set "PAGE=journey.html"
set "UI_URL=http://127.0.0.1:8080/%PAGE%#/dashboard"
set "API_DOCS_URL=http://127.0.0.1:8000/docs"
set "API_HEALTH_URL=http://127.0.0.1:8000/health"
set "PROXY_UI_URL=http://127.0.0.1:8317/management.html"

echo ==============================================
echo AI Trade Analyst bootstrap v3
echo Repo root: %ROOT%
echo ==============================================
echo.

if not exist "%APP_DIR%\%PAGE%" (
    echo ERROR: Could not find "%APP_DIR%\%PAGE%"
    echo Put this batch file in the repo root and try again.
    pause
    exit /b 1
)

if not exist "%ROOT%\ai_analyst\api\main.py" (
    echo ERROR: Could not find "%ROOT%\ai_analyst\api\main.py"
    echo Backend entrypoint is missing.
    pause
    exit /b 1
)

if not exist "%ROOT%\app\data\journeys" mkdir "%ROOT%\app\data\journeys" 2>nul
if not exist "%ROOT%\app\data\journeys\drafts" mkdir "%ROOT%\app\data\journeys\drafts" 2>nul
if not exist "%ROOT%\app\data\journeys\decisions" mkdir "%ROOT%\app\data\journeys\decisions" 2>nul
if not exist "%ROOT%\app\data\journeys\results" mkdir "%ROOT%\app\data\journeys\results" 2>nul

call :ensure_venv
if errorlevel 1 goto :fail

call :ensure_core_deps
if errorlevel 1 goto :fail

call :ensure_proxy
if errorlevel 1 (
    echo WARNING: CLIProxyAPI could not be confirmed on 8317.
    echo Continuing anyway. LLM-backed calls may fail until the proxy is started.
)

call :start_backend
if errorlevel 1 goto :fail

call :wait_for_http_ok "%API_HEALTH_URL%" 20
if errorlevel 1 (
    echo WARNING: Backend did not confirm healthy on /health within timeout.
)

call :start_ui
if errorlevel 1 goto :fail

echo.
echo Waiting briefly for UI server to come up...
timeout /t 2 /nobreak >nul

echo Opening browser tabs...
start "" "%UI_URL%"
start "" "%API_DOCS_URL%"
call :port_in_use 8317
if not errorlevel 1 start "" "%PROXY_UI_URL%"

echo.
echo ==============================================
echo Bootstrap complete
echo UI:      %UI_URL%
echo Backend: %API_DOCS_URL%
echo Proxy:   %PROXY_UI_URL%
echo ==============================================
echo.
pause
exit /b 0

:ensure_venv
echo [1/5] Ensuring virtual environment...
if exist "%VENV_PY%" (
    echo Found .venv
    exit /b 0
)

echo .venv not found. Creating it...
where py >nul 2>nul
if %errorlevel%==0 (
    py -m venv .venv
) else (
    where python >nul 2>nul
    if %errorlevel%==0 (
        python -m venv .venv
    ) else (
        echo ERROR: Python not found in PATH.
        exit /b 1
    )
)

if not exist "%VENV_PY%" (
    echo ERROR: Failed to create .venv
    exit /b 1
)

echo .venv created successfully.
exit /b 0

:ensure_core_deps
echo.
echo [2/5] Checking backend dependencies...

set "MISSING=0"

"%VENV_PY%" -c "import importlib.util,sys; sys.exit(0 if importlib.util.find_spec('fastapi') else 1)" >nul 2>nul
if errorlevel 1 (
    echo - Missing: fastapi
    set "MISSING=1"
)

"%VENV_PY%" -c "import importlib.util,sys; sys.exit(0 if importlib.util.find_spec('uvicorn') else 1)" >nul 2>nul
if errorlevel 1 (
    echo - Missing: uvicorn
    set "MISSING=1"
)

"%VENV_PY%" -c "import importlib.util,sys; sys.exit(0 if importlib.util.find_spec('dotenv') else 1)" >nul 2>nul
if errorlevel 1 (
    echo - Missing: python-dotenv
    set "MISSING=1"
)

"%VENV_PY%" -c "import importlib.util,sys; sys.exit(0 if importlib.util.find_spec('langgraph') else 1)" >nul 2>nul
if errorlevel 1 (
    echo - Missing: langgraph
    set "MISSING=1"
)

"%VENV_PY%" -c "import importlib.util,sys; sys.exit(0 if importlib.util.find_spec('multipart') else 1)" >nul 2>nul
if errorlevel 1 (
    echo - Missing: python-multipart
    set "MISSING=1"
)

if "%MISSING%"=="0" (
    echo Core dependencies already present.
    exit /b 0
)

echo Installing missing core dependencies...
"%VENV_PY%" -m pip install --upgrade pip --quiet
if errorlevel 1 (
    echo ERROR: pip upgrade failed.
    exit /b 1
)

"%VENV_PY%" -m pip install --quiet fastapi "uvicorn[standard]" python-dotenv langgraph python-multipart
if errorlevel 1 (
    echo ERROR: dependency installation failed.
    exit /b 1
)

echo Dependencies installed successfully.
exit /b 0

:ensure_proxy
echo.
echo [3/5] Ensuring CLIProxyAPI / model proxy on port 8317...
call :port_in_use 8317
if not errorlevel 1 (
    echo Proxy already appears to be running on 8317.
    exit /b 0
)

set "PROXY_EXE="
set "PROXY_DIR="

if exist "C:\cliproxyapi\cli-proxy-api.exe" (
    set "PROXY_EXE=C:\cliproxyapi\cli-proxy-api.exe"
    set "PROXY_DIR=C:\cliproxyapi"
)

if not defined PROXY_EXE (
    where cli-proxy-api.exe >nul 2>nul
    if %errorlevel%==0 (
        for /f "delims=" %%I in ('where cli-proxy-api.exe') do (
            set "PROXY_EXE=%%I"
            goto :proxy_check
        )
    )
)

if not defined PROXY_EXE (
    where cliproxyapi >nul 2>nul
    if %errorlevel%==0 (
        for /f "delims=" %%I in ('where cliproxyapi') do (
            set "PROXY_EXE=%%I"
            goto :proxy_check
        )
    )
)

if not defined PROXY_EXE (
    if exist "%LOCALAPPDATA%\Programs\CLIProxyAPI\cli-proxy-api.exe" (
        set "PROXY_EXE=%LOCALAPPDATA%\Programs\CLIProxyAPI\cli-proxy-api.exe"
        set "PROXY_DIR=%LOCALAPPDATA%\Programs\CLIProxyAPI"
    )
)

:proxy_check
if not defined PROXY_EXE (
    echo Proxy executable not found on PATH or in common locations.
    echo Expected one of:
    echo   C:\cliproxyapi\cli-proxy-api.exe
    echo   cli-proxy-api.exe
    echo   cliproxyapi
    exit /b 1
)

if not defined PROXY_DIR (
    for %%I in ("%PROXY_EXE%") do set "PROXY_DIR=%%~dpI"
)

echo Starting proxy from:
echo   !PROXY_DIR!
echo Using executable:
echo   !PROXY_EXE!

start "CLIProxyAPI" cmd /k "cd /d !PROXY_DIR! && !PROXY_EXE!"

echo Waiting for proxy confirmation on 8317...
call :wait_for_port 8317 20
if errorlevel 1 (
    echo Proxy did not confirm on 8317 within timeout.
    exit /b 1
)

echo Proxy confirmed on 8317.
exit /b 0

:start_backend
echo.
echo [4/5] Ensuring backend server on port 8000...
call :port_in_use 8000
if not errorlevel 1 (
    echo Backend already appears to be running on 8000.
    exit /b 0
)

echo Starting backend...
start "AI Trade Analyst Backend" cmd /k "cd /d "%ROOT%" && "%VENV_PY%" -m uvicorn ai_analyst.api.main:app --reload --host 127.0.0.1 --port 8000"
exit /b 0

:start_ui
echo.
echo [5/5] Ensuring UI server on port 8080...
call :port_in_use 8080
if not errorlevel 1 (
    echo UI server already appears to be running on 8080.
    exit /b 0
)

echo Starting UI server...
start "AI Trade Analyst UI" cmd /k "cd /d %APP_DIR% && %VENV_PY% -m http.server 8080 --bind 127.0.0.1"
exit /b 0

:port_in_use
netstat -ano | findstr /R /C:":%~1 .*LISTENING" >nul
exit /b %errorlevel%

:wait_for_port
set "WAIT_PORT=%~1"
set "WAIT_SECS=%~2"
set /a COUNT=0
:wait_port_loop
call :port_in_use %WAIT_PORT%
if not errorlevel 1 exit /b 0
if !COUNT! GEQ %WAIT_SECS% exit /b 1
set /a COUNT+=1
timeout /t 1 /nobreak >nul
goto :wait_port_loop

:wait_for_http_ok
set "WAIT_URL=%~1"
set "WAIT_SECS=%~2"
set /a COUNT=0
:wait_http_loop
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $r = Invoke-WebRequest -UseBasicParsing -Uri '%WAIT_URL%' -TimeoutSec 2; if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 400) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>nul
if not errorlevel 1 exit /b 0
if !COUNT! GEQ %WAIT_SECS% exit /b 1
set /a COUNT+=1
timeout /t 1 /nobreak >nul
goto :wait_http_loop

:fail
echo.
echo Bootstrap failed.
pause
exit /b 1