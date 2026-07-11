"""
JARVIS SYSTEM INITIALIZER
Startet alle JARVIS-Komponenten und koordiniert das System
"""

import os
import sys
import json
import subprocess
from pathlib import Path
import threading
import time
from datetime import datetime

# ============================================================================
# KONFIGURATION
# ============================================================================

class SystemConfig:
    PROJECT_ROOT = Path("E:/Mark-XXXIX-main")
    VAULT_PATH = PROJECT_ROOT / "vault"
    LOGS_PATH = PROJECT_ROOT / ".logs"
    STATE_FILE = PROJECT_ROOT / ".boss_engagement_state"
    
    # Module
    MODULES = {
        "JARVIS CORE": "jarvis_core.py",
        "COMPOSIO INTEGRATION": "jarvis_composio.py",
        "ENGAGEMENT ENGINE": "jarvis_engagement.py",
        "MASTER ORCHESTRATOR": "jarvis_master.py"
    }


# ============================================================================
# SYSTEM-INITIATOR
# ============================================================================

class JarvisSystemInit:
    """JARVIS-Systemstart"""
    
    def __init__(self):
        self.logs_path = SystemConfig.LOGS_PATH
        self.logs_path.mkdir(exist_ok=True)
    
    def log(self, message: str, level: str = "INFO"):
        """Log-Eintrag"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] [{level}] {message}"
        
        print(log_message)
        
        # In Logdatei schreiben
        logfile = self.logs_path / "jarvis_system.log"
        with open(logfile, "a", encoding="utf-8") as f:
            f.write(log_message + "\n")
    
    def check_environment(self) -> bool:
        """Umgebung überprüfen"""
        self.log("═"*70, "STARTUP")
        self.log("Überprüfe JARVIS-Umgebung...", "INFO")
        
        checks = {
            "Project Root": SystemConfig.PROJECT_ROOT.exists(),
            "Vault": SystemConfig.VAULT_PATH.exists(),
            "Logs": self.logs_path.exists(),
        }
        
        all_good = True
        for check_name, result in checks.items():
            status = "✓" if result else "✗"
            self.log(f"  {status} {check_name}", "CHECK")
            if not result:
                all_good = False
        
        return all_good
    
    def check_dependencies(self) -> bool:
        """Python-Dependencies überprüfen"""
        self.log("Überprüfe Dependencies...", "INFO")
        
        required_packages = [
            "openai",
            "pillow",
            "requests",
            "pyautogui",
            "composio",
        ]
        
        missing = []
        
        for package in required_packages:
            try:
                __import__(package)
                self.log(f"  ✓ {package}", "CHECK")
            except ImportError:
                self.log(f"  ✗ {package} (MISSING)", "WARN")
                missing.append(package)
        
        if missing:
            self.log(f"Installiere fehlende Packages: {', '.join(missing)}", "WARN")
            try:
                subprocess.run([sys.executable, "-m", "pip", "install"] + missing, check=True)
                self.log("✓ Dependencies installiert", "INFO")
                return True
            except subprocess.CalledProcessError:
                self.log("✗ Fehler beim Installieren von Dependencies", "ERROR")
                return False
        
        return True
    
    def check_api_keys(self) -> bool:
        """API-Keys überprüfen"""
        self.log("Überprüfe API-Keys...", "INFO")
        
        env_file = SystemConfig.PROJECT_ROOT / ".env"
        
        if not env_file.exists():
            self.log("⚠️  .env-Datei nicht gefunden!", "WARN")
            self.log("Bitte erstelle .env mit:", "INFO")
            self.log("  OPENAI_API_KEY=...", "INFO")
            self.log("  COMPOSIO_API_KEY=...", "INFO")
            self.log("  GEMINI_API_KEY=...", "INFO")
            return False
        
        # .env laden
        from dotenv import load_dotenv
        load_dotenv(env_file)
        
        keys = {
            "OPENAI_API_KEY": "OpenAI",
            "COMPOSIO_API_KEY": "Composio",
            "GEMINI_API_KEY": "Gemini",
        }
        
        all_present = True
        for env_var, service in keys.items():
            value = os.getenv(env_var)
            if value:
                self.log(f"  ✓ {service}", "CHECK")
            else:
                self.log(f"  ✗ {service} (Missing)", "WARN")
                all_present = False
        
        return all_present
    
    def initialize_state(self):
        """Initialisiere Boss-State"""
        self.log("Initialisiere Boss State...", "INFO")
        
        state_file = SystemConfig.STATE_FILE
        
        if not state_file.exists():
            default_state = {
                "last_interaction": datetime.now().isoformat(),
                "last_activity": "system_init",
                "inactivity_alerts_sent": [],
                "current_mood": "ready",
                "tasks_completed_today": 0
            }
            
            with open(state_file, 'w') as f:
                json.dump(default_state, f, indent=2)
            
            self.log("✓ Boss State initialisiert", "INFO")
        else:
            with open(state_file) as f:
                state = json.load(f)
                self.log(f"✓ Boss State geladen (Tasks: {state['tasks_completed_today']})", "INFO")
    
    def load_modules(self) -> bool:
        """Module laden und überprüfen"""
        self.log("Überprüfe JARVIS-Module...", "INFO")
        
        for module_name, module_file in SystemConfig.MODULES.items():
            module_path = SystemConfig.PROJECT_ROOT / module_file
            
            if module_path.exists():
                self.log(f"  ✓ {module_name}", "CHECK")
            else:
                self.log(f"  ✗ {module_name} (NOT FOUND: {module_file})", "WARN")
        
        return True
    
    def startup_banner(self):
        """JARVIS Start-Banner"""
        banner = """
╔═══════════════════════════════════════════════════════════════════════════╗
║                                                                             ║
║                      🤖 JARVIS CORE ENGINE 🤖                             ║
║                     Personal AI Assistant — Boss Mode                      ║
║                                                                             ║
║                      "Good morning, Boss."                                 ║
║                                                                             ║
║  ✓ Sprachsteuerung (Whisper)                                              ║
║  ✓ Bildschirmverständnis (GPT-4 Vision)                                   ║
║  ✓ Maus-/Tastatursteuerung (PyAutoGUI)                                    ║
║  ✓ Download-Assistent                                                      ║
║  ✓ Web-Recherche                                                           ║
║  ✓ Trading-Agent (Überwachung)                                            ║
║  ✓ Hintergrund-Automation                                                 ║
║                                                                             ║
╚═══════════════════════════════════════════════════════════════════════════╝
"""
        print(banner)
        self.log(banner, "STARTUP")
    
    def run_startup_checks(self) -> bool:
        """Vollständiger Startup-Prozess"""
        self.startup_banner()
        
        checks = [
            ("Umgebung", self.check_environment),
            ("Dependencies", self.check_dependencies),
            ("API-Keys", self.check_api_keys),
            ("Module", self.load_modules),
        ]
        
        all_passed = True
        for check_name, check_func in checks:
            try:
                if not check_func():
                    all_passed = False
            except Exception as e:
                self.log(f"✗ {check_name} fehlgeschlagen: {e}", "ERROR")
                all_passed = False
        
        self.initialize_state()
        
        print("\n")
        if all_passed:
            self.log("✓ ALLE CHECKS BESTANDEN", "SUCCESS")
            self.log("🚀 JARVIS ist bereit!", "STARTUP")
            return True
        else:
            self.log("✗ Einige Checks fehlgeschlagen", "ERROR")
            return False
    
    def start_core_engine(self):
        """Starte JARVIS Core"""
        self.log("Starte JARVIS Core Engine...", "INFO")
        
        try:
            # Importiere und starte jarvis_core
            os.chdir(SystemConfig.PROJECT_ROOT)
            
            from jarvis_core import JarvisCore
            
            jarvis = JarvisCore()
            jarvis.run_interactive()
        
        except Exception as e:
            self.log(f"✗ Fehler beim Starten: {e}", "ERROR")


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    import dotenv
    
    # .env laden
    dotenv.load_dotenv()
    
    system_init = JarvisSystemInit()
    
    # Startup-Checks
    if system_init.run_startup_checks():
        # Starte JARVIS Core
        system_init.start_core_engine()
    else:
        system_init.log("❌ JARVIS konnte nicht starten", "ERROR")
        sys.exit(1)
