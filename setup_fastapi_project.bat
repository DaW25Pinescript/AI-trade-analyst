@echo off
setlocal ENABLEDELAYEDEXPANSION

echo ======================================
echo FastAPI setup for Windows
 echo ======================================

afterPath:
set /p PROJECT_DIR=Enter full project folder path: 
if "%PROJECT_DIR%"=="" (
    echo You must enter a project path.
    goto afterPath
)
if not exist "%PROJECT_DIR%" (
    echo Project folder does not exist:
    echo %PROJECT_DIR%
    pause
    exit /b 1
)

cd /d "%PROJECT_DIR%"

echo.
set /p ENV_NAME=Enter virtual environment name [my_env]: 
if "%ENV_NAME%"=="" set ENV_NAME=my_env

echo.
echo [1/5] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo Python was not found in PATH.
    echo Install Python 3.8+ and make sure "Add Python to PATH" is enabled.
    pause
    exit /b 1
)

echo [2/5] Creating virtual environment "%ENV_NAME%"...
python -m venv "%ENV_NAME%"
if errorlevel 1 (
    echo Failed to create virtual environment.
    pause
    exit /b 1
)

echo [3/5] Activating virtual environment...
call "%PROJECT_DIR%\%ENV_NAME%\Scripts\activate.bat"
if errorlevel 1 (
    echo Failed to activate virtual environment.
    pause
    exit /b 1
)

echo [4/5] Installing FastAPI and Uvicorn...
python -m pip install --upgrade pip
python -m pip install fastapi "uvicorn[standard]"
if errorlevel 1 (
    echo Package installation failed.
    pause
    exit /b 1
)

if not exist "%PROJECT_DIR%\main.py" (
    echo [5/5] Creating starter main.py...
    > "%PROJECT_DIR%\main.py" echo from fastapi import FastAPI
    >> "%PROJECT_DIR%\main.py" echo.
    >> "%PROJECT_DIR%\main.py" echo app = FastAPI^(^)
    >> "%PROJECT_DIR%\main.py" echo.
    >> "%PROJECT_DIR%\main.py" echo @app.get^("/"^)
    >> "%PROJECT_DIR%\main.py" echo def read_root^(^):
    >> "%PROJECT_DIR%\main.py" echo     return {"Hello": "World"}
) else (
    echo [5/5] main.py already exists - leaving it unchanged.
)

echo.
echo Setup complete.
echo.
echo Starting FastAPI server at http://127.0.0.1:8000
echo Press Ctrl+C to stop the server.
echo.
python -m uvicorn main:app --reload

echo.
pause
endlocal
