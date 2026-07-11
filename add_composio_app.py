import sys
import json
import webbrowser
from pathlib import Path
from composio import Composio

def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent

BASE_DIR = get_base_dir()
API_CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"

def get_composio_key() -> str:
    try:
        with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("composio_api_key", "")
    except Exception:
        return ""

def main():
    print("===================================================")
    print("Composio App Hinzufuegen (Windows-Version)")
    print("===================================================")
    
    key = get_composio_key()
    if not key:
        print("[Fehler] Kein Composio API-Key in config/api_keys.json gefunden.")
        input("\nDruecke Enter zum Beenden...")
        return
        
    app_name = input("\nWelche App moechtest du verbinden? (z.B. gmail, github, slack): ").strip().lower()
    if not app_name:
        print("Keine App angegeben.")
        input("\nDruecke Enter zum Beenden...")
        return
        
    print(f"\nVerbinde {app_name}...")
    try:
        client = Composio(api_key=key, dangerously_skip_version_check=True)
        try:
            ac_id = client.toolkits._get_auth_config_id(toolkit=app_name)
        except Exception:
            ac_id = app_name
            
        print("Erstelle Verbindungslink...")
        conn_req = client.connected_accounts.link(user_id="default", auth_config_id=ac_id)
        url = getattr(conn_req, "redirect_url", None)
        
        if url:
            print(f"\nVerbindungslink erstellt: {url}")
            print("Oeffne Browser fuer die Autorisierung...")
            webbrowser.open(url)
        else:
            print("\n[Fehler] Es konnte kein Verbindungslink generiert werden.")
            
    except Exception as e:
        print(f"\n[Fehler] Verbindung fehlgeschlagen: {e}")
        
    input("\nDruecke Enter zum Beenden...")

if __name__ == "__main__":
    main()
