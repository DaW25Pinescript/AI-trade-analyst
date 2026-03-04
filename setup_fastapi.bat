@echo off
setlocal ENABLEDELAYEDEXPANSION

title FastAPI Setup and Run - V2

echo.
echo ==========================================
echo   FastAPI Setup and Run - V2
echo   (reload excludes virtual environment)
echo ==========================================
echo.

set /p PROJECT_DIR=Enter your project folder path: 
if "%PROJECT_DIR%"=="" (
    echo ERROR: No project folder entered.
    pause
    exit /b 1
)

if not exist "%PROJECT_DIR%" (
    echo ERROR: Project folder does not exist:
    echo %PROJECT_DIR%
    pause
    exit /b 1
)

cd /d "%PROJECT_DIR%"

set /p ENV_NAME=Enter virtual environment name [my_env]: 
if "%ENV_NAME%"=="" set ENV_NAME=my_env

echo.
echo Project folder: %PROJECT_DIR%
echo Virtual environment: %ENV_NAME%
echo.

if not exist "%ENV_NAME%\Scripts\activate.bat" (
    echo Creating virtual environment...
    py -m venv "%ENV_NAME%" 2>nul
    if errorlevel 1 (
        python -m venv "%ENV_NAME%"
        if errorlevel 1 (
            echo ERROR: Failed to create virtual environment.
            echo Make sure Python is installed and added to PATH.
            pause
            exit /b 1
        )
    )
) else (
    echo Virtual environment already exists.
)

echo.
echo Activating virtual environment...
call "%ENV_NAME%\Scripts\activate.bat"
if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment.
    pause
    exit /b 1
)

echo.
echo Upgrading pip...
python -m pip install --upgrade pip

echo.
echo Installing FastAPI and Uvicorn...
pip install fastapi "uvicorn[standard]"

if errorlevel 1 (
    echo ERROR: Package installation failed.
    pause
    exit /b 1
)

if not exist "main.py" (
    echo.
    echo Creating starter main.py ...
    > main.py echo from fastapi import FastAPI
    >> main.py echo.
    >> main.py echo app = FastAPI()
    >> main.py echo.
    >> main.py echo @app.get^("/")
    >> main.py echo def read_root^(^):
    >> main.py echo     return {"Hello": "World"}
) else (
    echo.
    echo main.py already exists. Leaving it unchanged.
)

echo.
echo Setup complete.
echo.
echo Starting FastAPI server at http://127.0.0.1:8000
echo Reload will exclude the virtual environment folder: %ENV_NAME%
echo Press Ctrl+C to stop the server.
echo.

uvicorn main:app --reload --reload-exclude "%ENV_NAME%"
