@echo off
REM ============================================
REM JARVIS Wake-Word Launcher
REM Startet Wake-Word Listener für "Jarvis wake up"
REM ============================================

setlocal enabledelayedexpansion

set "PYTHON_PATH=C:\Users\tanso\AppData\Local\Programs\Python\Python312\python.exe"
set "PROJECT_PATH=E:\Mark-XXXIX-main"
set "SCRIPT_PATH=%PROJECT_PATH%\wake_word_launcher.py"

echo.
echo ==========================================
echo   JARVIS Wake-Word Listener
echo ==========================================
echo.

if not exist "%PYTHON_PATH%" (
    echo ERROR: Python not found!
    echo Expected: %PYTHON_PATH%
    exit /b 1
)

if not exist "%PROJECT_PATH%" (
    echo ERROR: Project not found!
    echo Expected: %PROJECT_PATH%
    exit /b 1
)

set PYTHONPATH=
set PYTHONHOME=

echo [LAUNCHER] Starting Wake-Word Listener...
echo [LISTENER] Say 'Jarvis wake up' to activate
echo.

cd /d "%PROJECT_PATH%"
"%PYTHON_PATH%" "%SCRIPT_PATH%"

pause
