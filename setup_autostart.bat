@echo off
REM ============================================
REM Create Windows Autostart Link for JARVIS
REM ============================================

setlocal enabledelayedexpansion

set "BAT_FILE=E:\Mark-XXXIX-main\clap_launcher.bat"
set "STARTUP_FOLDER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "SHORTCUT_NAME=JARVIS-ClapListener.lnk"

REM Check ob Batch-Datei existiert
if not exist "%BAT_FILE%" (
    echo ERROR: clap_launcher.bat nicht gefunden!
    echo Expected: %BAT_FILE%
    pause
    exit /b 1
)

REM Erstelle VBS-Script zum Erstellen des Links
set "VBS_FILE=%TEMP%\create_link.vbs"

(
    echo Set oWS = WScript.CreateObject("WScript.Shell"^)
    echo sLinkFile = "%STARTUP_FOLDER%\%SHORTCUT_NAME%"
    echo Set oLink = oWS.CreateShortcut(sLinkFile^)
    echo oLink.TargetPath = "%BAT_FILE%"
    echo oLink.WorkingDirectory = "E:\Mark-XXXIX-main"
    echo oLink.Description = "JARVIS Clap Listener - Auto Start"
    echo oLink.WindowStyle = 1
    echo oLink.Save
    echo MsgBox "Autostart link created successfully!" ^& vbNewLine ^& "Shortcut: " ^& sLinkFile, 64, "Success"
) > "%VBS_FILE%"

REM Führe VBS aus
cscript "%VBS_FILE%"
del "%VBS_FILE%"

echo.
echo ==========================================
echo Autostart configured!
echo.
echo Next time Windows starts, JARVIS will be
echo listening for a hand clap to activate.
echo.
echo Shortcut location:
echo %STARTUP_FOLDER%\%SHORTCUT_NAME%
echo ==========================================
echo.
pause
