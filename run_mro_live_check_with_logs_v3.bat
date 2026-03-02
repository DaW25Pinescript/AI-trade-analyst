@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM ==========================================
REM AI Trade Analyst - MRO Live Check Runner v3
REM - Saves separate JSON per instrument
REM - Saves one combined log file
REM - Writes a compact summary block at the end
REM ==========================================

cd /d "%~dp0"

REM Force UTF-8 for Python stdout/stderr on Windows
set "PYTHONIOENCODING=utf-8"

REM Timestamp
for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "STAMP=%%I"

REM Paths
set "LOGDIR=%~dp0logs"
if not exist "%LOGDIR%" mkdir "%LOGDIR%"

set "LOGFILE=%LOGDIR%\mro_live_check_%STAMP%.log"
set "SUMMARYFILE=%LOGDIR%\mro_summary_%STAMP%.txt"

REM Default instrument if no arg passed
set "MAIN_INSTRUMENT=%~1"
if "%MAIN_INSTRUMENT%"=="" set "MAIN_INSTRUMENT=XAUUSD"

echo ========================================== > "%LOGFILE%"
echo AI Trade Analyst - MRO Live Check Runner v3 >> "%LOGFILE%"
echo ========================================== >> "%LOGFILE%"
echo Log file: %LOGFILE% >> "%LOGFILE%"
echo Summary file: %SUMMARYFILE% >> "%LOGFILE%"
echo Main instrument: %MAIN_INSTRUMENT% >> "%LOGFILE%"
echo. >> "%LOGFILE%"

echo ==========================================
echo AI Trade Analyst - MRO Live Check Runner v3
echo ==========================================
echo Log file: %LOGFILE%
echo Summary file: %SUMMARYFILE%
echo Main instrument: %MAIN_INSTRUMENT%
echo.

REM Activate local venv if present
if exist ".venv\Scripts\activate.bat" (
    echo Activating .venv ...
    echo Activating .venv ... >> "%LOGFILE%"
    call ".venv\Scripts\activate.bat" >> "%LOGFILE%" 2>&1
) else (
    echo No .venv found. Continuing with system Python...
    echo No .venv found. Continuing with system Python... >> "%LOGFILE%"
)
echo. >> "%LOGFILE%"

REM Prompt for keys only if not already set
if "%FINNHUB_API_KEY%"=="" (
    set /p FINNHUB_API_KEY=Enter FINNHUB_API_KEY: 
)
if "%FRED_API_KEY%"=="" (
    set /p FRED_API_KEY=Enter FRED_API_KEY: 
)
echo Keys loaded in current session. >> "%LOGFILE%"

echo Installing MRO requirements...
echo Installing MRO requirements... >> "%LOGFILE%"
python -m pip install -r macro_risk_officer\requirements.txt >> "%LOGFILE%" 2>&1
if errorlevel 1 (
    echo ERROR: Failed to install requirements.
    echo ERROR: Failed to install requirements. >> "%LOGFILE%"
    goto :end
)

echo. > "%SUMMARYFILE%"
echo ========================================== >> "%SUMMARYFILE%"
echo MRO RUN SUMMARY >> "%SUMMARYFILE%"
echo Timestamp: %STAMP% >> "%SUMMARYFILE%"
echo ========================================== >> "%SUMMARYFILE%"
echo. >> "%SUMMARYFILE%"

call :run_one "%MAIN_INSTRUMENT%"
call :run_one "EURUSD"
call :run_one "NAS100"
call :run_one "USOIL"

echo.
echo Running tests ...
echo Running tests ... >> "%LOGFILE%"
python -m pytest -q macro_risk_officer/tests >> "%LOGFILE%" 2>&1
if errorlevel 1 (
    echo WARNING: Some tests failed. Check log.
    echo WARNING: Some tests failed. Check log. >> "%LOGFILE%"
    echo Tests: FAILED >> "%SUMMARYFILE%"
    goto :end
) else (
    echo Tests: PASSED >> "%SUMMARYFILE%"
)

echo.
echo All steps completed successfully.
echo All steps completed successfully. >> "%LOGFILE%"

:end
echo. >> "%LOGFILE%"
echo Finished. >> "%LOGFILE%"
echo Share these with ChatGPT or Codex: >> "%LOGFILE%"
echo   %LOGFILE% >> "%LOGFILE%"
echo   %SUMMARYFILE% >> "%LOGFILE%"
echo   logs\mro_status_*.json >> "%LOGFILE%"

echo.
echo Finished.
echo Share these with ChatGPT or Codex:
echo   %LOGFILE%
echo   %SUMMARYFILE%
echo   logs\mro_status_*.json
pause
exit /b

:run_one
set "INSTRUMENT=%~1"
set "SAFE_INSTRUMENT=%INSTRUMENT:/=_%"
set "JSONFILE=%LOGDIR%\mro_status_%SAFE_INSTRUMENT%_%STAMP%.json"

echo.
echo Running JSON status for %INSTRUMENT% ...
echo Running JSON status for %INSTRUMENT% ... >> "%LOGFILE%"
python -m macro_risk_officer status --instrument "%INSTRUMENT%" --json > "%JSONFILE%" 2>> "%LOGFILE%"
if errorlevel 1 (
    echo ERROR: JSON status failed for %INSTRUMENT%.
    echo ERROR: JSON status failed for %INSTRUMENT%. >> "%LOGFILE%"
    echo %INSTRUMENT% : FAILED >> "%SUMMARYFILE%"
    goto :eof
)

echo Saved JSON: %JSONFILE%
echo Saved JSON: %JSONFILE% >> "%LOGFILE%"
type "%JSONFILE%" >> "%LOGFILE%"

REM Extract top-level fields using PowerShell JSON parsing
for /f "usebackq delims=" %%A in (`powershell -NoProfile -Command "$j = Get-Content -Raw '%JSONFILE%' ^| ConvertFrom-Json; [string]$j.regime"`) do set "REGIME=%%A"
for /f "usebackq delims=" %%A in (`powershell -NoProfile -Command "$j = Get-Content -Raw '%JSONFILE%' ^| ConvertFrom-Json; [string]$j.vol_bias"`) do set "VOLBIAS=%%A"
for /f "usebackq delims=" %%A in (`powershell -NoProfile -Command "$j = Get-Content -Raw '%JSONFILE%' ^| ConvertFrom-Json; [string]$j.conflict_score"`) do set "CONFLICT=%%A"
for /f "usebackq delims=" %%A in (`powershell -NoProfile -Command "$j = Get-Content -Raw '%JSONFILE%' ^| ConvertFrom-Json; [string]$j.confidence"`) do set "CONFIDENCE=%%A"
for /f "usebackq delims=" %%A in (`powershell -NoProfile -Command "$j = Get-Content -Raw '%JSONFILE%' ^| ConvertFrom-Json; if ($j.active_event_ids) { ($j.active_event_ids -join ', ') }"`) do set "EVENTS=%%A"

if "%EVENTS%"=="" set "EVENTS=(none)"

echo %INSTRUMENT% >> "%SUMMARYFILE%"
echo   regime: %REGIME% >> "%SUMMARYFILE%"
echo   vol_bias: %VOLBIAS% >> "%SUMMARYFILE%"
echo   conflict_score: %CONFLICT% >> "%SUMMARYFILE%"
echo   confidence: %CONFIDENCE% >> "%SUMMARYFILE%"
echo   active_event_ids: %EVENTS% >> "%SUMMARYFILE%"
echo   json_file: %JSONFILE% >> "%SUMMARYFILE%"
echo. >> "%SUMMARYFILE%"

echo Running human-readable status for %INSTRUMENT% ... >> "%LOGFILE%"
python -m macro_risk_officer status --instrument "%INSTRUMENT%" >> "%LOGFILE%" 2>&1
if errorlevel 1 (
    echo WARNING: Human-readable status failed for %INSTRUMENT%. >> "%LOGFILE%"
)
goto :eof
