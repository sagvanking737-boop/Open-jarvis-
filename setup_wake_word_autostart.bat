@echo off
REM Create Autostart for Wake-Word Listener

setlocal enabledelayedexpansion

set "BAT_FILE=E:\Mark-XXXIX-main\wake_word_launcher.bat"
set "STARTUP_FOLDER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "SHORTCUT_NAME=JARVIS-WakeWordListener.lnk"

if not exist "%BAT_FILE%" (
    echo ERROR: wake_word_launcher.bat not found!
    pause
    exit /b 1
)

set "VBS_FILE=%TEMP%\create_wakeword_link.vbs"

(
    echo Set oWS = WScript.CreateObject("WScript.Shell"^)
    echo sLinkFile = "%STARTUP_FOLDER%\%SHORTCUT_NAME%"
    echo Set oLink = oWS.CreateShortcut(sLinkFile^)
    echo oLink.TargetPath = "%BAT_FILE%"
    echo oLink.WorkingDirectory = "E:\Mark-XXXIX-main"
    echo oLink.Description = "JARVIS Wake-Word Listener"
    echo oLink.WindowStyle = 1
    echo oLink.Save
    echo MsgBox "Autostart configured!", 64, "Success"
) > "%VBS_FILE%"

cscript "%VBS_FILE%"
del "%VBS_FILE%"

echo.
echo Autostart link created:
echo %STARTUP_FOLDER%\%SHORTCUT_NAME%
echo.
pause
