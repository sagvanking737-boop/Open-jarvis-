@echo off
REM ========================================================================
REM JARVIS CORE ENGINE STARTER
REM Windows Batch Launcher
REM ========================================================================

setlocal enabledelayedexpansion

REM Setze Working Directory
cd /d "E:\Mark-XXXIX-main" || (
    echo ERROR: Kann nicht zu E:\Mark-XXXIX-main wechseln
    pause
    exit /b 1
)

REM Python-Path explizit setzen (verhindert Hermes-Pollution)
set PYTHONPATH=
set PYTHONHOME=

REM Finde Python
for /f "delims=" %%i in ('where python.exe') do set PYTHON=%%i

if "!PYTHON!"=="" (
    echo ERROR: Python nicht gefunden
    echo Bitte installiere Python: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo.
echo ========================================================================
echo  JARVIS CORE ENGINE STARTER
echo ========================================================================
echo.
echo Python: !PYTHON!
echo WorkDir: %CD%
echo.

REM Überprüfe .env
if not exist ".env" (
    echo ERROR: .env-Datei nicht gefunden
    echo Bitte erstelle .env mit:
    echo   OPENAI_API_KEY=...
    echo   COMPOSIO_API_KEY=...
    echo   GEMINI_API_KEY=...
    pause
    exit /b 1
)

echo ✓ .env gefunden
echo.
echo Starte JARVIS...
echo.

REM Starte JARVIS System Initializer
"!PYTHON!" jarvis_system_init.py

if errorlevel 1 (
    echo.
    echo ERROR: JARVIS konnte nicht starten
    pause
    exit /b 1
)

pause
