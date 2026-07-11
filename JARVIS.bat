@echo off
REM ============================================================================
REM JARVIS — MASTER LAUNCHER
REM ============================================================================
REM Boss Mode Batch Launcher für vollständiges JARVIS VISION System
REM Deutsch-erste Befehle, interaktives Menü, alles aus einer Datei
REM ============================================================================

setlocal enabledelayedexpansion

set PYTHONPATH=
set JARVIS_HOME=%~dp0
set JARVIS_LOG=%JARVIS_HOME%\.logs
set JARVIS_DATA=%JARVIS_HOME%\.data

REM ============================================================================
REM INITIALIZATION
REM ============================================================================

if not exist "%JARVIS_LOG%" mkdir "%JARVIS_LOG%"
if not exist "%JARVIS_DATA%" mkdir "%JARVIS_DATA%"

title JARVIS VISION — Boss Mode
color 0A
cls

echo.
echo ================================================================================
echo  JARVIS VISION — PERSOENLICHER KI-ASSISTENT
echo ================================================================================
echo.
echo  Guten Abend, Boss. Ein produktiver Tag geht zu Ende.
echo.
echo  Loading...
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo  [FEHLER] Python nicht gefunden!
    echo  Bitte installieren Sie Python 3.11+ von python.org
    pause
    exit /b 1
)

REM Check erforderliche Module
python -c "import openai" >nul 2>&1
if errorlevel 1 (
    echo  [INFO] Installiere fehlende Pakete...
    pip install openai pillow requests -q
)

echo.
echo ================================================================================
echo  HAUPTMENU
echo ================================================================================
echo.
echo  1. Trading (Autonomous Trading aktivieren/steuern)
echo  2. Download (Anwendungen herunterladen und installieren)
echo  3. Research (Web-Recherche durchführen)
echo  4. Bildschirm (Screenshot-Analyse)
echo  5. Status (System-Überwachung und Logs)
echo  6. Einstellungen (Konfiguration, API-Keys, etc.)
echo  7. Sprachbefehl (Interaktive Sprachsteuerung)
echo  0. Beenden
echo.

:menu
echo.
set /p choice="Deine Wahl (0-7): "

if "%choice%"=="1" goto trading_menu
if "%choice%"=="2" goto download_menu
if "%choice%"=="3" goto research_menu
if "%choice%"=="4" goto screen_menu
if "%choice%"=="5" goto status_menu
if "%choice%"=="6" goto settings_menu
if "%choice%"=="7" goto voice_menu
if "%choice%"=="0" goto shutdown

echo  [!] Ungueltige Eingabe
goto menu

REM ============================================================================
REM TRADING MENU
REM ============================================================================
:trading_menu
cls
echo.
echo ================================================================================
echo  AUTONOMOUS TRADING
echo ================================================================================
echo.
echo  1. Trading starten (Background)
echo  2. Manueller Trade (BTC, ETH, etc.)
echo  3. Trading-Ueberwachung starten
echo  4. Alle Trades anzeigen
echo  5. Trading deaktivieren
echo  6. Zurück zum Menü
echo.

set /p trade_choice="Deine Wahl (1-6): "

if "%trade_choice%"=="1" (
    echo.
    echo  [*] Starte Autonomous Trading...
    cd /d "%JARVIS_HOME%"
    python -c "from jarvis_core import JarvisCore; j = JarvisCore(); print('Trading Agent aktiviert')"
    goto trading_menu
)

if "%trade_choice%"=="2" (
    echo.
    set /p symbol="Symbol eingeben (z.B. BTC, ETH): "
    set /p side="Seite (BUY/SELL): "
    set /p qty="Menge: "
    set /p price="Preis (oder ENTER fuer Market): "
    
    echo.
    echo  [*] Fuehre Trade aus: !symbol! !side! !qty!
    
    cd /d "%JARVIS_HOME%"
    python << PYTHON_TRADE
import sys
sys.path.insert(0, '.')
from jarvis_core import TradingAgent

agent = TradingAgent()
result = agent.execute_trade("!symbol!", "!side!".lower(), float("!qty!"))
print(f"\nTrade Status: {result['status']}")
PYTHON_TRADE
    
    goto trading_menu
)

if "%trade_choice%"=="3" (
    echo.
    echo  [*] Starte TradingMonitor-Agent...
    cd /d "%JARVIS_HOME%"
    python -c "from jarvis_background_agents import TradingMonitorAgent; m = TradingMonitorAgent(); m.watch_symbol('BTC'); print('BTC wird ueberwacht...')"
    goto trading_menu
)

if "%trade_choice%"=="4" (
    echo.
    echo  [*] Listing aller ausgeführten Trades...
    cd /d "%JARVIS_HOME%"
    python << PYTHON_LIST_TRADES
import sys
sys.path.insert(0, '.')
from jarvis_core import TradingAgent
agent = TradingAgent()
trades = agent.get_executed_trades()
for i, t in enumerate(trades, 1):
    print(f"{i}. {t['side'].upper()} {t['quantity']}x {t['symbol']} @ {t.get('price', 'MARKET')}")
PYTHON_LIST_TRADES
    goto trading_menu
)

if "%trade_choice%"=="5" (
    echo.
    echo  [!] Trading DEAKTIVIERT (Safety Mode)
    cd /d "%JARVIS_HOME%"
    python -c "from jarvis_core import TradingAgent; a = TradingAgent(); a.trading_enabled = False; print('Trading disabled')"
    goto trading_menu
)

if "%trade_choice%"=="6" (
    goto menu
)

echo  [!] Ungueltige Eingabe
goto trading_menu

REM ============================================================================
REM DOWNLOAD MENU
REM ============================================================================
:download_menu
cls
echo.
echo ================================================================================
echo  DOWNLOAD ASSISTANT
echo ================================================================================
echo.
echo  Beliebt:
echo  - blender    (3D-Modellierung)
echo  - python     (Programmiersprache)
echo  - git        (Versionskontrolle)
echo  - vscode     (Code-Editor)
echo  - nodejs     (JavaScript Runtime)
echo  - firefox    (Web-Browser)
echo.

set /p app="App herunterladen (z.B. blender, oder ENTER zurück): "

if "%app%"=="" goto menu

echo.
echo  [*] Starte Download: %app%...

cd /d "%JARVIS_HOME%"
python << PYTHON_DOWNLOAD
import sys
sys.path.insert(0, '.')
from jarvis_core import DownloadAssistant

assistant = DownloadAssistant()
url = assistant.find_download_link("%app%")
if url:
    print(f"[+] Found: {url}")
    success = assistant.download_file(url)
    if success:
        print("[+] Download erfolgreich")
    else:
        print("[-] Download fehlgeschlagen")
else:
    print("[-] App nicht gefunden")
PYTHON_DOWNLOAD

goto download_menu

REM ============================================================================
REM RESEARCH MENU
REM ============================================================================
:research_menu
cls
echo.
echo ================================================================================
echo  WEB-RECHERCHE
echo ================================================================================
echo.

set /p query="Recherchiere nach (oder ENTER zurück): "

if "%query%"=="" goto menu

echo.
echo  [*] Suche: %query%...

cd /d "%JARVIS_HOME%"
python << PYTHON_RESEARCH
import sys
sys.path.insert(0, '.')
from jarvis_core import WebResearch

research = WebResearch()
results = research.google_search("%query%")
print(f"\n[+] {len(results)} Ergebnisse gefunden:")
for i, r in enumerate(results[:5], 1):
    print(f"\n{i}. {r.get('title', 'N/A')}")
    print(f"   {r.get('link', 'N/A')}")
    print(f"   {r.get('snippet', 'N/A')[:100]}...")
PYTHON_RESEARCH

goto research_menu

REM ============================================================================
REM SCREEN ANALYSIS MENU
REM ============================================================================
:screen_menu
cls
echo.
echo ================================================================================
echo  BILDSCHIRM-ANALYSE
echo ================================================================================
echo.
echo  1. Screenshot machen und analysieren
echo  2. Aktive Fenster erkennen
echo  3. Text auf Bildschirm lesen (OCR)
echo  4. Zurück
echo.

set /p screen_choice="Deine Wahl (1-4): "

if "%screen_choice%"=="1" (
    echo.
    echo  [*] Mache Screenshot...
    cd /d "%JARVIS_HOME%"
    python -c "from jarvis_core import ScreenUnderstanding; s = ScreenUnderstanding(); img = s.capture_screen(); print('[+] Screenshot erfasst')"
    goto screen_menu
)

if "%screen_choice%"=="2" (
    echo.
    echo  [*] Erkenne Windows...
    cd /d "%JARVIS_HOME%"
    python -c "from jarvis_core import ScreenUnderstanding; s = ScreenUnderstanding(); windows = s.detect_windows(); print(f'[+] {len(windows)} Fenster erkannt')"
    goto screen_menu
)

if "%screen_choice%"=="3" (
    echo.
    echo  [*] Lese Text (OCR)...
    cd /d "%JARVIS_HOME%"
    python -c "from jarvis_core import ScreenUnderstanding; s = ScreenUnderstanding(); text = s.extract_text(); print('[+] Text extrahiert')"
    goto screen_menu
)

if "%screen_choice%"=="4" (
    goto menu
)

goto screen_menu

REM ============================================================================
REM STATUS MENU
REM ============================================================================
:status_menu
cls
echo.
echo ================================================================================
echo  SYSTEM STATUS
echo ================================================================================
echo.

cd /d "%JARVIS_HOME%"
python << PYTHON_STATUS
import sys, os
from pathlib import Path
sys.path.insert(0, '.')

print("\n[*] JARVIS Status:")
print(f"    Home: E:\\Mark-XXXIX-main")
print(f"    Python: {sys.version.split()[0]}")
print(f"    Temp: C:\\Users\\tanso\\AppData\\Local\\Temp")

try:
    from jarvis_core import JarvisCore
    j = JarvisCore()
    print(f"    State: OK")
    print(f"    Tasks today: {j.state.tasks_completed_today}")
except Exception as e:
    print(f"    State: ERROR ({e})")

# Check logs
log_dir = Path(".logs")
if log_dir.exists():
    logs = list(log_dir.glob("*.log"))
    print(f"    Logs: {len(logs)} files")
else:
    print(f"    Logs: Not found")

print()
PYTHON_STATUS

pause
goto menu

REM ============================================================================
REM SETTINGS MENU
REM ============================================================================
:settings_menu
cls
echo.
echo ================================================================================
echo  EINSTELLUNGEN
echo ================================================================================
echo.
echo  1. API-Keys prüfen
echo  2. .env editieren
echo  3. State zurücksetzen
echo  4. Logs löschen
echo  5. Zurück
echo.

set /p settings_choice="Deine Wahl (1-5): "

if "%settings_choice%"=="1" (
    echo.
    echo  [*] Prüfe API-Keys in .env...
    if exist .env (
        echo  [+] .env vorhanden
        findstr /I "KEY" .env
    ) else (
        echo  [-] .env nicht gefunden
    )
    pause
    goto settings_menu
)

if "%settings_choice%"=="2" (
    echo.
    echo  [*] Öffne .env im Editor...
    start notepad .env
    pause
    goto settings_menu
)

if "%settings_choice%"=="3" (
    echo.
    echo  [!] Setze State zurück...
    del .data\state.json 2>nul
    echo  [+] State zurückgesetzt
    pause
    goto settings_menu
)

if "%settings_choice%"=="4" (
    echo.
    echo  [!] Lösche Logs...
    del .logs\*.log 2>nul
    echo  [+] Logs gelöscht
    pause
    goto settings_menu
)

if "%settings_choice%"=="5" (
    goto menu
)

goto settings_menu

REM ============================================================================
REM VOICE MENU
REM ============================================================================
:voice_menu
cls
echo.
echo ================================================================================
echo  SPRACHSTEUERUNG (Interaktiv)
echo ================================================================================
echo.
echo  Beispiele:
echo  - "Trading bitcoin"
echo  - "Lade Blender herunter"
echo  - "Recherchiere Kubernetes"
echo  - "Zeige Screenshot"
echo  - "quit" zum Beenden
echo.

cd /d "%JARVIS_HOME%"
python << PYTHON_VOICE
import sys
sys.path.insert(0, '.')
from jarvis_core import VoiceControl, JarvisCore

voice = VoiceControl()
jarvis = JarvisCore()

print("\n[*] Sprachsteuerung aktiv (quit zum Beenden)\n")

while True:
    cmd_text = input(">> ").strip()
    
    if cmd_text.lower() == "quit":
        print("\n[+] Auf Wiedersehen, Boss!")
        break
    
    if not cmd_text:
        continue
    
    try:
        cmd = voice.parse_command(cmd_text)
        result = jarvis.execute_command(cmd)
        if result:
            print(f"[+] Befehl ausgeführt")
    except Exception as e:
        print(f"[-] Fehler: {e}")

PYTHON_VOICE

goto menu

REM ============================================================================
REM SHUTDOWN
REM ============================================================================
:shutdown
echo.
echo ================================================================================
echo  JARVIS finishing...
echo ================================================================================
echo.
echo  Auf Wiedersehen, Boss. Bis zum nächsten Mal.
echo.
timeout /t 2 /nobreak
exit /b 0
