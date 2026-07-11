@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
chcp 65001 >nul

set PYTHONUTF8=1
set PYTHONPATH=
set PYTHONNOUSERSITE=1
set PIP_DISABLE_PIP_VERSION_CHECK=1
set QT_LOGGING_RULES=qt.qpa.window=false
set "PYTHON=C:\Users\tanso\AppData\Local\Programs\Python\Python312\python.exe"

echo ================================================
echo   J.A.R.V.I.S - MARK XXXIX Ultimate Edition
echo ================================================
echo.

if not exist "%PYTHON%" (
    echo [ERROR] Python 3.12 not found at:
    echo %PYTHON%
    pause
    exit /b 1
)

"%PYTHON%" --version
echo [OK] Python ready
echo.

echo [SETUP] Checking dependencies...
"%PYTHON%" -m pip --disable-pip-version-check install -r requirements.txt --quiet
if errorlevel 1 (
    echo [WARN] pip install failed, trying core packages...
    "%PYTHON%" -m pip --disable-pip-version-check install sounddevice google-genai pyautogui PyQt6 pyperclip psutil openai pillow --quiet
)
"%PYTHON%" -m playwright install chromium >nul 2>nul
echo.

echo [CHECK] Verifying core modules...
"%PYTHON%" -c "import agent.time_awareness, agent.self_awareness, agent.screen_agent, agent.auto_trader, agent.openrouter_client"
if errorlevel 1 (
    echo [WARN] Some core modules have issues, starting anyway...
) else (
    echo [OK] Core modules ready
)
echo.

echo [START] Launching MARK XXXIX...
echo.
"%PYTHON%" main.py

if errorlevel 1 (
    echo.
    echo [ERROR] MARK XXXIX stopped with exit code %errorlevel%
    echo Log: .logs\jarvis.log
    echo.
    pause
)
