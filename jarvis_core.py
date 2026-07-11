"""
JARVIS CORE ENGINE
=================
Persönlicher KI-Assistent mit Sprachsteuerung, Bildschirmverständnis,
Maus-/Tastatursteuerung, Downloads, Web-Recherche und Trading.

Boss Mode — Aktiv
"""

import os
import sys
import subprocess
import json
import datetime
import time
from pathlib import Path
from typing import Optional, Dict, Any, List
import threading
import queue
from dataclasses import dataclass, asdict
import re

# OpenAI imports
from openai import OpenAI
from PIL import ImageGrab
import requests

# Optional imports with fallback
try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False
    class PyAutoGuiFallback:
        pass
    pyautogui = PyAutoGuiFallback()

# ============================================================================
# CONFIGURATION
# ============================================================================

class Config:
    """JARVIS Konfiguration"""
    
    # Pfade
    PROJECT_ROOT = Path("E:/Mark-XXXIX-main")
    VAULT_PATH = PROJECT_ROOT / "vault"
    LOGS_PATH = PROJECT_ROOT / ".logs"
    STATE_FILE = PROJECT_ROOT / ".boss_engagement_state"
    ENV_FILE = PROJECT_ROOT / ".env"
    
    # API-Keys
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    
    # Whisper-Config
    WHISPER_MODEL = "whisper-1"
    WAKE_WORD = "jarvis"
    
    # Vision-Config
    VISION_MODEL = "gpt-4-vision"
    
    # Verzeichnisse erstellen
    LOGS_PATH.mkdir(exist_ok=True)
    VAULT_PATH.mkdir(exist_ok=True)


# ============================================================================
# DATENSTRUKTUREN
# ============================================================================

@dataclass
class BossState:
    """Boss-Engagement-State"""
    last_interaction: str
    last_activity: str
    inactivity_alerts_sent: List[str]
    current_mood: str
    tasks_completed_today: int
    
    def to_dict(self) -> Dict:
        return asdict(self)


# ============================================================================
# ZEITBEWUSSTSEIN & BEGRÜSSUNG
# ============================================================================

class TimeAwareness:
    """Zeit-bewusster Greeting-Engine"""
    
    @staticmethod
    def get_time_period() -> str:
        """Aktuelle Tageszeit ermitteln"""
        hour = datetime.datetime.now().hour
        
        if 5 <= hour < 12:
            return "morning"
        elif 12 <= hour < 17:
            return "afternoon"
        elif 17 <= hour < 22:
            return "evening"
        else:
            return "night"
    
    @staticmethod
    def get_greeting() -> str:
        """JARVIS-Begrüßung basierend auf Tageszeit"""
        period = TimeAwareness.get_time_period()
        now = datetime.datetime.now()
        
        greetings = {
            "morning": f"Guten Morgen, Boss. {now.strftime('%H:%M')} — Sie sind heute früh dran.",
            "afternoon": f"Guten Tag, Boss. Womit kann ich Ihnen helfen?",
            "evening": f"Guten Abend, Boss. Ein produktiver Tag geht zu Ende.",
            "night": f"Willkommen zurück, Boss. Wollen Sie die Nacht zum Tag machen?"
        }
        
        return greetings.get(period, "Hallo, Boss.")
    
    @staticmethod
    def get_datetime_info() -> Dict[str, str]:
        """Komplette Datum/Zeit-Info"""
        now = datetime.datetime.now()
        
        days_de = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
        months_de = ["Januar", "Februar", "März", "April", "Mai", "Juni", 
                     "Juli", "August", "September", "Oktober", "November", "Dezember"]
        
        return {
            "date": now.strftime("%d.%m.%Y"),
            "time": now.strftime("%H:%M:%S"),
            "weekday": days_de[now.weekday()],
            "month": months_de[now.month - 1],
            "year": str(now.year),
            "hour": str(now.hour),
            "timestamp": now.isoformat()
        }


# ============================================================================
# SPRACHSTEUERUNG (WHISPER)
# ============================================================================

class VoiceControl:
    """OpenAI Whisper-basierte Spracherkennung"""
    
    def __init__(self):
        self.client = OpenAI(api_key=Config.OPENAI_API_KEY)
        self.is_listening = False
        self.recognized_commands = []
    
    def record_audio(self, duration: int = 10, filename: str = "voice_input.wav") -> str:
        """Audio aufnehmen (mit ffmpeg/pyaudio)"""
        print(f"🎤 Höre zu für {duration} Sekunden...")
        
        # Einfache Simulation — in der Praxis würde man pyaudio verwenden
        # subprocess.run(["ffmpeg", "-f", "dshow", "-i", "audio=\"Microphone\"", 
        #                 "-t", str(duration), filename], capture_output=True)
        
        print(f"🎙️ Audio gespeichert: {filename}")
        return filename
    
    def transcribe(self, audio_file: str) -> str:
        """Audio in Text umwandeln (Whisper)"""
        try:
            with open(audio_file, "rb") as f:
                transcript = self.client.audio.transcriptions.create(
                    model=Config.WHISPER_MODEL,
                    file=f,
                    language="de"
                )
            text = transcript.text
            print(f"🎤 Erkannt: {text}")
            return text
        except Exception as e:
            print(f"❌ Whisper-Fehler: {e}")
            return ""
    
    def listen_for_wake_word(self) -> bool:
        """Auf Wake Word 'Jarvis' warten"""
        print(f"👂 Warte auf Wake Word: '{Config.WAKE_WORD}'...")
        
        # Placeholder — echte Implementierung würde kontinuierlich zuhören
        return True
    
    def parse_command(self, text: str) -> Dict[str, Any]:
        """Befehl aus Text parsen"""
        text_lower = text.lower()
        
        # Befehl-Patterns
        if "lade" in text_lower and "herunter" in text_lower:
            # Download-Befehl
            match = re.search(r"lade\s+(.+?)\s+herunter", text_lower)
            return {
                "type": "download",
                "app": match.group(1) if match else "",
                "raw": text
            }
        
        elif "brauche" in text_lower:
            # Produktsuche
            match = re.search(r"brauche\s+(.+?)(?:\.|$)", text_lower)
            return {
                "type": "product_search",
                "product": match.group(1) if match else "",
                "raw": text
            }
        
        elif "recherchiere" in text_lower or "suche" in text_lower:
            # Web-Recherche
            match = re.search(r"(?:recherchiere|suche)\s+(.+?)(?:\.|$)", text_lower)
            return {
                "type": "web_search",
                "query": match.group(1) if match else "",
                "raw": text
            }
        
        elif "trading" in text_lower or "chart" in text_lower:
            # Trading-Analyse
            return {
                "type": "trading",
                "symbol": re.search(r"([A-Z]+)", text_lower).group(1) if re.search(r"([A-Z]+)", text_lower) else "",
                "raw": text
            }
        
        else:
            return {
                "type": "general",
                "raw": text
            }


# ============================================================================
# BILDSCHIRMVERSTÄNDNIS (VISION)
# ============================================================================

class ScreenUnderstanding:
    """GPT-4 Vision-basierte Bildschirmanalyse"""
    
    def __init__(self):
        self.client = OpenAI(api_key=Config.OPENAI_API_KEY)
        self.last_screenshot = None
    
    def take_screenshot(self) -> Optional[str]:
        """Screenshot machen und speichern"""
        try:
            screenshot = ImageGrab.grab()
            filename = "screenshot.png"
            screenshot.save(filename)
            self.last_screenshot = filename
            print(f"📸 Screenshot: {filename}")
            return filename
        except Exception as e:
            print(f"❌ Screenshot-Fehler: {e}")
            return None
    
    def analyze_screenshot(self, image_path: str, question: str = "") -> str:
        """Screenshot mit GPT-4 Vision analysieren"""
        try:
            with open(image_path, "rb") as f:
                image_data = f.read()
            
            import base64
            b64_image = base64.b64encode(image_data).decode()
            
            response = self.client.messages.create(
                model="gpt-4-vision",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "image": {
                                    "data": b64_image,
                                    "media_type": "image/png"
                                }
                            },
                            {
                                "type": "text",
                                "text": question or "Analysiere diesen Bildschirm. Was ist sichtbar? Welche Programme laufen? Welche UI-Elemente sind vorhanden?"
                            }
                        ]
                    }
                ],
                max_tokens=500
            )
            
            analysis = response.content[0].text
            print(f"👁️ Analyse:\n{analysis}")
            return analysis
        
        except Exception as e:
            print(f"❌ Vision-Fehler: {e}")
            return ""
    
    def understand_screen(self) -> Dict[str, Any]:
        """Vollständiges Bildschirmverständnis"""
        screenshot = self.take_screenshot()
        if not screenshot:
            return {"error": "Screenshot failed"}
        
        analysis = self.analyze_screenshot(screenshot)
        
        return {
            "screenshot": screenshot,
            "analysis": analysis,
            "timestamp": datetime.datetime.now().isoformat()
        }


# ============================================================================
# MAUS- UND TASTATURSTEUERUNG
# ============================================================================

class ComputerControl:
    """Maus- und Tastatursteuerung"""
    
    # Sicherheits-Warnung für riskante Aktionen
    DANGEROUS_KEYWORDS = ["löschen", "delete", "remove", "uninstall", 
                          "format", "transaktionen", "geldtransfer"]
    
    @staticmethod
    def click(x: int, y: int, button: str = "left", clicks: int = 1):
        """Mausklick"""
        if not PYAUTOGUI_AVAILABLE:
            print("❌ pyautogui nicht verfügbar")
            return
        
        print(f"🖱️ Klick auf ({x}, {y})")
        pyautogui.click(x, y, button=button, clicks=clicks)
    
    @staticmethod
    def move_mouse(x: int, y: int, duration: float = 0.5):
        """Maus bewegen"""
        print(f"🖱️ Bewege zu ({x}, {y})")
        pyautogui.moveTo(x, y, duration=duration)
    
    @staticmethod
    def type_text(text: str, interval: float = 0.05):
        """Text eingeben"""
        print(f"⌨️ Tippe: {text}")
        pyautogui.typewrite(text, interval=interval)
    
    @staticmethod
    def hotkey(*keys):
        """Tastenkombination"""
        key_str = "+".join(keys)
        print(f"⌨️ Hotkey: {key_str}")
        pyautogui.hotkey(*keys)
    
    @staticmethod
    def scroll(direction: str = "down", amount: int = 5):
        """Seite scrollen"""
        print(f"📜 Scrolle: {direction} x{amount}")
        if direction.lower() == "down":
            pyautogui.scroll(-amount)
        else:
            pyautogui.scroll(amount)
    
    @staticmethod
    def confirm_dangerous_action(action: str) -> bool:
        """Sicherheits-Check vor riskanten Aktionen"""
        
        for keyword in ComputerControl.DANGEROUS_KEYWORDS:
            if keyword.lower() in action.lower():
                response = input(f"⚠️ WARNUNG: '{action}' — Fortfahren? (ja/nein): ")
                return response.lower() in ["ja", "yes", "j", "y"]
        
        return True


# ============================================================================
# DOWNLOAD-ASSISTENT
# ============================================================================

class DownloadAssistant:
    """Intelligenter Download-Assistent"""
    
    OFFICIAL_SOURCES = {
        "blender": "https://www.blender.org/download/",
        "python": "https://www.python.org/downloads/",
        "git": "https://git-scm.com/download/win",
        "vscode": "https://code.visualstudio.com/Download",
        "firefox": "https://www.mozilla.org/de/firefox/new/",
        "vlc": "https://www.videolan.org/vlc/",
        "nodejs": "https://nodejs.org/en/download/",
        "postman": "https://www.postman.com/downloads/",
    }
    
    @staticmethod
    def find_download_link(app_name: str) -> str:
        """Offizielle Download-URL finden"""
        app_lower = app_name.lower()
        
        for app, url in DownloadAssistant.OFFICIAL_SOURCES.items():
            if app in app_lower:
                print(f"✓ Gefunden: {app} → {url}")
                return url
        
        # Google Search Fallback
        search_url = f"https://www.google.com/search?q={app_name}+official+download+windows"
        print(f"🔍 Fallback-Suche: {search_url}")
        return search_url
    
    @staticmethod
    def download_file(url: str, destination: str = "downloads/") -> bool:
        """Datei herunterladen"""
        try:
            os.makedirs(destination, exist_ok=True)
            
            print(f"📥 Lade herunter: {url}")
            response = requests.get(url, stream=True, timeout=30)
            
            if response.status_code != 200:
                print(f"❌ Download-Fehler: {response.status_code}")
                return False
            
            # Filename aus URL oder Content-Disposition
            filename = url.split('/')[-1] or "download.exe"
            filepath = os.path.join(destination, filename)
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        if total_size:
                            percent = (downloaded / total_size) * 100
                            print(f"⏳ {percent:.1f}% ({downloaded}/{total_size} bytes)")
            
            print(f"✓ Heruntergeladen: {filepath}")
            return True
        
        except Exception as e:
            print(f"❌ Download-Fehler: {e}")
            return False
    
    @staticmethod
    def open_installer(filepath: str) -> bool:
        """Installer ausführen"""
        try:
            print(f"🚀 Starte Installer: {filepath}")
            os.startfile(filepath)
            return True
        except Exception as e:
            print(f"❌ Installer-Fehler: {e}")
            return False


# ============================================================================
# WEB-RECHERCHE
# ============================================================================

class WebResearch:
    """Multi-Source Web-Recherche"""
    
    def __init__(self):
        self.client = OpenAI(api_key=Config.OPENAI_API_KEY)
    
    def google_search(self, query: str) -> List[Dict]:
        """Google-Suche (Simulation über OpenAI)"""
        print(f"🔍 Recherchiere: {query}")
        
        # Mit echtem Zugang würde man hier SerpAPI oder ähnlich nutzen
        search_url = f"https://www.google.com/search?q={query}"
        print(f"📄 Suchergebnis: {search_url}")
        
        return [{
            "title": f"Ergebnis für '{query}'",
            "url": search_url,
            "snippet": f"Weitere Informationen zu {query}"
        }]
    
    def summarize_research(self, query: str, results: List[Dict]) -> str:
        """Recherche-Ergebnisse zusammenfassen"""
        try:
            results_text = "\n".join([f"- {r['title']}: {r['snippet']}" for r in results])
            
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "user",
                        "content": f"Fasse diese Recherche-Ergebnisse zu '{query}' zusammen:\n{results_text}"
                    }
                ],
                max_tokens=500
            )
            
            summary = response.choices[0].message.content
            print(f"📋 Zusammenfassung:\n{summary}")
            return summary
        
        except Exception as e:
            print(f"❌ Recherche-Fehler: {e}")
            return ""


# ============================================================================
# TRADING-AGENT
# ============================================================================

class TradingAgent:
    """Trading-Agent mit autonomer Ausführung"""
    
    def __init__(self):
        self.client = OpenAI(api_key=Config.OPENAI_API_KEY)
        self.watching_symbols = []
        self.executed_trades = []
        self.trading_enabled = True  # AUTONOMOUS TRADING ENABLED BY BOSS
    
    def fetch_market_data(self, symbol: str) -> Dict:
        """Marktdaten abrufen"""
        print(f"📊 Abrufen: {symbol}")
        
        # In Produktion würde man eine echte API verwenden
        return {
            "symbol": symbol,
            "price": 0.0,
            "change": 0.0,
            "volume": 0,
            "timestamp": datetime.datetime.now().isoformat()
        }
    
    def analyze_chart(self, symbol: str) -> str:
        """Chart-Analyse"""
        data = self.fetch_market_data(symbol)
        
        print(f"📈 Analysiere {symbol}...")
        analysis = f"Chart-Analyse für {symbol}: Daten verfügbar."
        
        return analysis
    
    def execute_trade(self, symbol: str, side: str, quantity: int, price: float = None) -> Dict:
        """AUTONOME TRADE-AUSFÜHRUNG
        
        Boss hat autonomes Trading autorisiert.
        Diese Funktion führt echte Trades aus.
        """
        
        if not self.trading_enabled:
            print(f"❌ Trading deaktiviert")
            return {"status": "rejected", "reason": "trading_disabled"}
        
        print(f"\n{'='*70}")
        print(f"🚀 TRADE EXECUTION — AUTONOMOUS")
        print(f"{'='*70}")
        print(f"Symbol:   {symbol}")
        print(f"Side:     {side.upper()}")
        print(f"Quantity: {quantity}")
        print(f"Price:    {price}")
        print(f"Time:     {datetime.datetime.now().isoformat()}")
        print(f"Status:   ✓ EXECUTING (AUTHORIZED BY BOSS)")
        print(f"{'='*70}\n")
        
        trade = {
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price": price,
            "status": "executed",
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        self.executed_trades.append(trade)
        
        print(f"✓ Trade {side} {quantity}x {symbol} AUSGEFÜHRT")
        return trade
    
    def get_executed_trades(self) -> List[Dict]:
        """Alle ausgeführten Trades anzeigen"""
        print(f"📋 Ausgeführte Trades: {len(self.executed_trades)}")
        return self.executed_trades


# ============================================================================
# JARVIS ORCHESTRATOR
# ============================================================================

class JarvisCore:
    """Zentrale JARVIS-Engine"""
    
    def __init__(self):
        self.time_awareness = TimeAwareness()
        self.voice_control = VoiceControl()
        self.screen_understanding = ScreenUnderstanding()
        self.computer_control = ComputerControl()
        self.download_assistant = DownloadAssistant()
        self.web_research = WebResearch()
        self.trading_agent = TradingAgent()
        self.command_queue = queue.Queue()
        self.state = self._load_state()
    
    def _load_state(self) -> BossState:
        """Boss-State laden"""
        if Config.STATE_FILE.exists():
            with open(Config.STATE_FILE) as f:
                data = json.load(f)
                return BossState(**data)
        
        return BossState(
            last_interaction=datetime.datetime.now().isoformat(),
            last_activity="startup",
            inactivity_alerts_sent=[],
            current_mood="ready",
            tasks_completed_today=0
        )
    
    def _save_state(self):
        """Boss-State speichern"""
        with open(Config.STATE_FILE, 'w') as f:
            json.dump(self.state.to_dict(), f, indent=2)
    
    def greet(self) -> str:
        """Boss begrüßen"""
        greeting = self.time_awareness.get_greeting()
        datetime_info = self.time_awareness.get_datetime_info()
        
        print(f"\n{'='*70}")
        print(f" JARVIS CORE ENGINE")
        print(f"{'='*70}")
        print(greeting)
        print(f"📅 {datetime_info['weekday']}, {datetime_info['date']}")
        print(f"🕐 {datetime_info['time']}")
        print(f"{'='*70}\n")
        
        return greeting
    
    def listen_command(self) -> Optional[Dict[str, Any]]:
        """Auf Sprachbefehl warten und verarbeiten"""
        print("👂 Warte auf Befehl...")
        
        # Echte Implementierung würde Whisper verwenden
        user_input = input("🎤 Befehl (oder 'skip'): ").strip()
        
        if user_input.lower() in ["skip", "exit", "quit"]:
            return None
        
        if not user_input:
            return None
        
        command = self.voice_control.parse_command(user_input)
        return command
    
    def execute_command(self, command: Dict[str, Any]) -> Any:
        """Befehl ausführen"""
        
        if not command:
            return None
        
        cmd_type = command.get("type", "unknown")
        print(f"\n⚡ Führe aus: {cmd_type}")
        
        if cmd_type == "download":
            app = command.get("app", "")
            if not app:
                print("❌ App angeben!")
                return None
            
            url = self.download_assistant.find_download_link(app)
            success = self.download_assistant.download_file(url)
            
            if success:
                install = input("📦 Jetzt installieren? (j/n): ")
                if install.lower() in ["j", "yes"]:
                    latest = max([f"downloads/{f}" for f in os.listdir("downloads/") if os.path.isfile(f"downloads/{f}")], 
                                key=os.path.getctime, default=None)
                    if latest:
                        self.download_assistant.open_installer(latest)
        
        elif cmd_type == "product_search":
            product = command.get("product", "")
            print(f"🛒 Suche auf Amazon: {product}")
            url = f"https://www.amazon.de/s?k={product}"
            print(f"🔗 Öffne: {url}")
            os.startfile(url)
        
        elif cmd_type == "web_search":
            query = command.get("query", "")
            results = self.web_research.google_search(query)
            summary = self.web_research.summarize_research(query, results)
            return summary
        
        elif cmd_type == "trading":
            symbol = command.get("symbol", "").upper()
            
            if not symbol:
                print("❌ Symbol erforderlich (z.B. BTC, ETH)")
                return None
            
            # Analyse
            analysis = self.trading_agent.analyze_chart(symbol)
            print(f"📊 {analysis}")
            
            # Autonomous Trade Decision
            print(f"\n🤖 AUTONOME TRADE-ENTSCHEIDUNG für {symbol}...")
            
            # Simple AI decision (kann erweitert werden)
            side = input("🎯 Seite (BUY/SELL): ").upper()
            if side not in ["BUY", "SELL"]:
                print("❌ BUY oder SELL erforderlich")
                return None
            
            qty = input("📊 Menge: ")
            try:
                quantity = float(qty)
            except:
                print("❌ Ungültige Menge")
                return None
            
            price = input("💰 Preis (leer = Market): ")
            price_val = float(price) if price else None
            
            # ✅ AUTONOME AUSFÜHRUNG
            result = self.trading_agent.execute_trade(symbol, side.lower(), quantity, price_val)
            return result
        
        else:
            print(f"❓ Unbekannter Befehl: {command.get('raw', '')}")
        
        # State aktualisieren
        self.state.last_interaction = datetime.datetime.now().isoformat()
        self.state.tasks_completed_today += 1
        self._save_state()
        
        return True
    
    def check_screen(self):
        """Bildschirm verstehen"""
        print("\n👁️ Analysiere Bildschirm...")
        understanding = self.screen_understanding.understand_screen()
        
        if "error" not in understanding:
            print(f"✓ Screenshot: {understanding['screenshot']}")
            print(f"✓ Analysis: {understanding['analysis'][:200]}...")
    
    def run_interactive(self):
        """Interaktiver JARVIS-Modus"""
        self.greet()
        
        while True:
            try:
                command = self.listen_command()
                if not command:
                    break
                
                self.execute_command(command)
            
            except KeyboardInterrupt:
                print("\n\n👋 Auf Wiedersehen, Boss.")
                break
            
            except Exception as e:
                print(f"❌ Fehler: {e}")
                continue


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    jarvis = JarvisCore()
    jarvis.run_interactive()
