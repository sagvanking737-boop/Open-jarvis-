@echo off
REM JARVIS Obsidian Brain — Quick Launcher
REM Opens Obsidian with JARVIS vault
REM Usage: Double-click or call from terminal

setlocal enabledelayedexpansion

SET VAULT_PATH=E:\Mark-XXXIX-main\vault
SET HERMES_HOME=%USERPROFILE%\.hermes

echo.
echo ========================================
echo   JARVIS Real Edition — Obsidian Brain
echo ========================================
echo.
echo Opening Obsidian vault:
echo %VAULT_PATH%
echo.

REM Open Obsidian with vault
start obsidian://open?path=%VAULT_PATH%

REM Load environment (API keys, etc.)
if exist "%VAULT_PATH%\..\..\.env" (
    echo Loading .env configuration...
)

echo.
echo ✓ Obsidian should open in a few seconds
echo ✓ Once open, you'll see the JARVIS Brain
echo.
echo Quick Navigation:
echo   • README.md — Start here (Main hub)
echo   • Daily/2026-07-05 — Today's check-in
echo   • Projects/YouTube-Strategy — Content strategy
echo   • Analytics/Dashboard — Real metrics
echo.
echo Close this window anytime.
pause
