@echo off
REM ============================================
REM JARVIS Auto-Clap Listener
REM Läuft beim PC-Start im Hintergrund
REM Wartet auf Handklatscher zum Starten
REM ============================================

setlocal enabledelayedexpansion

set "PYTHON_PATH=C:\Users\tanso\AppData\Local\Programs\Python\Python312\python.exe"
set "PROJECT_PATH=E:\Mark-XXXIX-main"
set "SCRIPT_PATH=%PROJECT_PATH%\clap_launcher.py"

echo.
echo ==========================================
echo   JARVIS Clap Listener - Auto Start
echo ==========================================
echo.

REM Check ob Python existiert
if not exist "%PYTHON_PATH%" (
    echo ERROR: Python nicht gefunden!
    echo Erwartet: %PYTHON_PATH%
    exit /b 1
)

REM Check ob Projekt existiert
if not exist "%PROJECT_PATH%" (
    echo ERROR: Projekt nicht gefunden!
    echo Erwartet: %PROJECT_PATH%
    exit /b 1
)

REM Setze Umgebung
set PYTHONPATH=
set PYTHONHOME=

REM Starte Clap Listener
echo [CLAP LISTENER] Starting...
echo [CLAP LISTENER] Waiting for hand clap to launch JARVIS...
echo [CLAP LISTENER] Clap once to start MARK-XXXIX!
echo.

cd /d "%PROJECT_PATH%"
"%PYTHON_PATH%" "%SCRIPT_PATH%"

REM Falls Script endet, halte Fenster offen
pause
