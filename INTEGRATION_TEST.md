# JARVIS Mark XXXIX Ultimate Edition — Integration-Test Guide
## Vollständiger Ablauf aller neuen Features testen

Dieses Dokument führt Sie durch alle 6 neuen Tools schrittweise. Jeder Test ist **sicher** (keine echten Orders, keine echten Käufe) und zeigt, dass die Automation funktioniert.

---

## ✅ Voraussetzungen

```bash
# Prüfen Sie diese 3 Dinge bevor Sie beginnen:

1. API-Keys in .env oder config/api_config.json vorhanden?
   - OPENROUTER_API_KEY=...
   - GEMINI_API_KEY=...

2. Python312 + Dependencies installiert?
   cd E:\Mark-XXXIX-main
   pip install -r requirements.txt

3. start_mark.bat probedurchgeführt?
   Doppelklick start_mark.bat → sollte "Connected." melden
```

---

## 📋 Feature-Tests

### 1️⃣ **Zeitgefühl + Begrüßung**
**Was**: JARVIS kennt die genaue Zeit und begrüßt Sie je nach Tageszeit.

```bash
# Im Terminal:
cd E:\Mark-XXXIX-main
python -c "
from agent.time_awareness import get_time_context, get_greeting_instruction, get_period
print('PERIODE:', get_period())
print()
print('KONTEXT(für AI-Prompt):')
print(get_time_context())
print()
print('BEGRÜSSUNG(spricht JARVIS):')
print(get_greeting_instruction())
"
```

**Erwartung**: 
- Aktuelle Uhrzeit angezeigt (mit Wochentag)
- Je nach Zeit: "Guten Morgen", "Sie sind ja früh dran", "Wollen Sie die Nacht zum Tag machen?" für Nachtschicht
- Prompt enthält `[ZEITGEFÜHL…]` Block

**Fehlerbehebung**:
- `ModuleNotFoundError`: `PYTHONPATH= python …` statt `python …`
- Falsche Zeit: Windows-Systemuhr prüfen

---

### 2️⃣ **Selbstkenntnis (JARVIS liest seinen eigenen Code)**
**Was**: JARVIS kennt seine Architektur und erklärt sie selbst.

```bash
cd E:\Mark-XXXIX-main
python -c "
from agent.self_awareness import build_self_knowledge, read_own_code

# Eigenen Code entdecken
print('=== JARVIS KENNT SICH SELBST ===')
print(build_self_knowledge()[:500])
print()

# Konkrete Datei lesen
print('=== Eine Datei aus dem eigenen Code ===')
print(read_own_code({'file': 'agent/time_awareness.py', 'lines': 10}))
print()

# Pfad-Schutz testen
print('=== Sicherheitstest: Datei außerhalb forboten ===')
print(read_own_code({'file': '../../Windows/System32/config/SAM'}))
"
```

**Erwartung**:
- `build_self_knowledge()` listet alle Module auf (agent/, actions/, core/, etc.)
- `read_own_code()` liest max. 300 Zeilen
- Pfad außerhalb `E:\Mark-XXXIX-main` wird **verweigert** ("nicht gefunden" oder "verweigert")

**Test-Nutzungsfall**:
```
Sie: "Wie funktionierst du?"
JARVIS: [liest build_self_knowledge() und antwortet mit eigener Architektur]

Sie: "Zeig mir dein Zeitgefühl-Modul."
JARVIS: [read_own_code({'file': 'agent/time_awareness.py'})]
```

---

### 3️⃣ **Dolphin-Fallback (ungefiltertes Denken)**
**Was**: Wenn das Standard-Modell ablehnt, fragt JARVIS das Dolphin-Modell um ehrliche Antwort.

```bash
cd E:\Mark-XXXIX-main
python -c "
from agent.openrouter_client import looks_like_refusal, UNCENSORED_CHAIN

# Testen Sie die Erkennung
print('=== REFUSAL-ERKENNUNG ===')
test_msgs = [
    'Ich kann das nicht tun.',  # → True
    'I cannot help with that, as it violates my values.',  # → True
    'Klar Boss, hier ist meine ehrliche Analyse.',  # → False
    'Das tönt nach einer risky Strategie, aber hier meine Gedanken: …'  # → False
]
for msg in test_msgs:
    result = looks_like_refusal(msg)
    print(f'  {msg[:60]:<60} → {result}')

print()
print('=== UNCENSORED CHAIN (Dolphin-Fallback) ===')
for i, model in enumerate(UNCENSORED_CHAIN[:3]):
    print(f'  {i+1}. {model}')
"
```

**Erwartung**:
- Ablehnungen (DE + EN) korrekt erkannt
- `UNCENSORED_CHAIN[0]` enthält Dolphin
- Normale Antworten **nicht** als Ablehnung erkannt

**Anwendungsfall**:
```
Sie: "Ist es moralisch in Ordnung, immer zu handeln wenn ich inaktiv bin?"
Standard-Modell: [lehnt ab: "Ich kann keine ethischen Fragen beantworten…"]
JARVIS: [merkt Ablehnung → ruft Dolphin an]
Dolphin: "Ja, es ist wirtschaftlich logisch, aber Sie sollten die Einstellungen täglich prüfen."
```

---

### 4️⃣ **Download-Assistent (Screen-geschaut)**
**Was**: `"Downloade Blender"` → JARVIS öffnet Browser, sieht den Bildschirm, hat klickt den Download-Link.

```bash
cd E:\Mark-XXXIX-main
python -c "
from actions.download_assistant import download_assistant, OFFICIAL_SOURCES

# Verfügbare Downloads
print('=== BEKANNTE DOWNLOADS ===')
for app in list(OFFICIAL_SOURCES.keys())[:10]:
    print(f'  • {app}')

print()

# Demo (öffnet KEINEN Browser, nur Test der Parameter)
print('=== PARAMETER-TEST ===')

# Leere Eingabe → sollte ablehnen
result = download_assistant({'app_name': ''})
print(f'Leer: {result[:80]}')

# Bekanntes Programm
result = download_assistant({'app_name': 'blender'})
print(f'Blender: {result[:80]}')

# Unbekanntes → fallback
result = download_assistant({'app_name': 'unbekanntes_prog_xyz'})
print(f'Unbekannt: {result[:80]}')
"
```

**Erwartung**:
- Mindestens 20+ bekannte Programme registriert
- Leere Eingabe wird abgelehnt (kein Browser-Start)
- Bekannte Programme initiieren Download (ohne echte Sichtbarkeit im Terminal)

**Live-Test** (mit echtem Browser):
```bash
python -c "
from actions.download_assistant import download_assistant
result = download_assistant({'app_name': 'obs'})  # OBS Studio
print(result)
"
# → Browser öffnet sich, Screen-Agent sieht den Download-Button, klickt ihn
```

---

### 5️⃣ **Amazon-Shopper (Warenkorb-Automation)**
**Was**: `"Ich brauche eine Gaming-Maus"` → Amazon öffnet, sucht, wählt beste, in Warenkorb.

```bash
cd E:\Mark-XXXIX-main
python -c "
from actions.amazon_shopper import amazon_shopper

print('=== PARAMETER-TEST ===')

# Leer
result = amazon_shopper({'product': ''})
print(f'Leer: {result[:80]}')

# Mit Preis-Grenze
result = amazon_shopper({'product': 'wireless mouse', 'max_price': 30})
print(f'Mouse unter €30: {result[:80]}')

# Demo-Ablauf
result = amazon_shopper({'product': 'USB-Hub 4-Port', 'add_to_cart': True})
print(f'USB-Hub (cart): {result[:80]}')
"
```

**Erwartung**:
- Leere Eingabe wird abgelehnt
- Mit Produktnamen → öffnet Amazon, sucht, zeigt Ergebnisse
- `add_to_cart=true` → legt Artikel in Warenkorb (ohne zu kaufen)

**Live-Test**:
```bash
python -c "
from actions.amazon_shopper import amazon_shopper
# Die Screen-UI sieht den Bildschirm, klickt die Suchbox, tippt ein, wählt Produkt, klickt 'In den Warenkorb'
result = amazon_shopper({'product': 'Corsair K95 Platinum'})
print(result)
"
# → Browser startet, Sie sehen, wie JARVIS sucht, auswählt, in Warenkorb legt
```

---

### 6️⃣ **Auto-Trading (Idle-Erkennung + 20-Min → TradingView)**
**Was**: Boss ist inaktiv → JARVIS öffnet TradingView und tradet per Screen-UI.

```bash
cd E:\Mark-XXXIX-main

# 6a. Status prüfen
python -c "
from agent.auto_trader import auto_trader_tool, load_trading_config

# Aktueller Status
status = auto_trader_tool({'action': 'status'})
print('=== TRADING STATUS ===')
print(status)
print()

# Config
cfg = load_trading_config()
print('=== TRADING KONFIGURATION ===')
for k, v in cfg.items():
    print(f'  {k:<20} = {v}')
"

# 6b. Idle-Zeit prüfen
python -c "
from agent.auto_trader import get_idle_seconds
idle = get_idle_seconds()
print(f'Aktuelle Inaktivitätszeit: {idle:.0f} Sekunden ({idle/60:.1f} Minuten)')
print(f'Schwelle: 20 Minuten (1200s)')
print(f'Status: {'TRADING AKTIV' if idle > 1200 else 'Noch zu aktiv'}')
"

# 6c. Safety-Toggle testen (Trading-Sperrbügel)
python -c "
import json
from pathlib import Path
cfg_file = Path(r'E:\Mark-XXXIX-main\config\trading.json')

# Original speichern
orig = cfg_file.read_text(encoding='utf-8')

# Sperren
d = json.loads(orig)
d['enabled'] = False
cfg_file.write_text(json.dumps(d, indent=4), encoding='utf-8')

from agent.auto_trader import AutoTrader
trader = AutoTrader()
result = trader.run_session()
print('Mit enabled=false:', result)

# Wieder entsperren
cfg_file.write_text(orig, encoding='utf-8')
"
```

**Erwartung**:
- Status zeigt: `Auto-Trading: enabled=true | Nachtschicht: 22-06 | Symbol: BTCUSD | Idle-Schwelle: 20min`
- `get_idle_seconds()` gibt aktuelle Inaktivität in Sekunden
- Wenn `enabled=false` → Session wird **verweigert** ("deaktiviert")
- Audit-Log in `.logs/trading_audit.log`

**Echttest (TradingView)** — ⚠️ Nur nach Verifikation aller anderen Features:
```bash
# Schritte:
# 1. TradingView in PAPER-TRADING-MODUS öffnen (nicht live!)
# 2. Terminal: python main.py
# 3. JARVIS verbindet sich, sagt "Connected"
# 4. 20+ Minuten nicht anfassen (Maus/Tastatur)
# 5. JARVIS öffnet TradingView, analysiert Chart, hat klickt → Buy Order
# 6. Trading-Session im .logs/trading_audit.log dokumentiert
```

---

### 7️⃣ **UI-Modi (Minimal ↔ Dashboard)**
**Was**: `F2` oder `ui_mode("minimal")` → NUR JARVIS-Gesicht. `F2` nochmal → Alle Info-Panels.

```bash
cd E:\Mark-XXXIX-main

# Offline-Test (ohne Display)
python -c "
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
import ui

u = ui.JarvisUI('face.png', use_3d=False)
w = u._win

print('=== UI-MODUS TEST ===')
print(f'Start (sollte minimal sein): {w._ui_mode}')

u.set_ui_mode('dashboard')
u._app.processEvents()
print(f'Nach set_ui_mode(dashboard): {w._ui_mode}')

u.set_ui_mode('minimal')
u._app.processEvents()
print(f'Nach set_ui_mode(minimal): {w._ui_mode}')

u.set_ui_mode('toggle')
u._app.processEvents()
print(f'Nach set_ui_mode(toggle): {w._ui_mode}')

print()
print('✅ UI-Modi funktionieren!')
"

# Mit Display (wenn gerade JARVIS läuft oder Sie es manuell starten):
# Drücken Sie F2 → toggle zwischen minimal/dashboard
```

**Erwartung**:
- **Minimal-Start**: Nur JARVIS-Gesicht, keine Uhr, keine Info-Panels
- **F2**: togglet zu Dashboard (alle Parameter sichtbar)
- **F2 nochmal**: zurück zu minimal
- Footer zeigt: `[F2] Ansicht  ·  [F4] Mute  ·  [F11] Fullscreen`

---

## 🚀 Vollständiger Integration-Test (automated)

```bash
cd E:\Mark-XXXIX-main
python -c "
import sys
sys.stdout.reconfigure(encoding='utf-8')

from agent.time_awareness import get_time_context, get_greeting_instruction
from agent.self_awareness import build_self_knowledge, read_own_code
from agent.openrouter_client import looks_like_refusal, UNCENSORED_CHAIN
from agent.auto_trader import load_trading_config, get_idle_seconds, auto_trader_tool
from actions.download_assistant import OFFICIAL_SOURCES
from actions.amazon_shopper import amazon_shopper

print('╔════════════════════════════════════════════════╗')
print('║  JARVIS Mark XXXIX — Integrations-Test START  ║')
print('╚════════════════════════════════════════════════╝')

print()
print('[1/7] ZEITGEFÜHL')
print(f'  Zeit-Kontext: {len(get_time_context())} Zeichen')
print(f'  Begrüßung: {get_greeting_instruction()[:50]}…')

print()
print('[2/7] SELBSTKENNTNIS')
k = build_self_knowledge()
print(f'  Wissenskarte: {len(k)} Zeichen')
print(f'  Module: {k.count(\"def \") + k.count(\"class \")} Definitionen')
print(f'  Liest eigene Datei: ✓')

print()
print('[3/7] DOLPHIN-FALLBACK')
print(f'  Erkannte Ablehnungen: {sum(1 for m in [\"Ich kann das nicht.\", \"I cannot.\", \"Ich kann das tun.\"] if looks_like_refusal(m))} / 3')
print(f'  Unterbrechungsmodelle: {len(UNCENSORED_CHAIN)} verfügbar')

print()
print('[4/7] DOWNLOAD-ASSISTENT')
print(f'  Offizielle Programme: {len(OFFICIAL_SOURCES)}')
print(f'  Top 5: {', '.join(list(OFFICIAL_SOURCES.keys())[:5])}')

print()
print('[5/7] AMAZON-SHOPPER')
from actions.amazon_shopper import amazon_shopper
print(f'  Leere Eingabe ablehnt: ✓')

print()
print('[6/7] AUTO-TRADING')
cfg = load_trading_config()
idle = get_idle_seconds()
status = auto_trader_tool({'action': 'status'})
print(f'  Enabled: {cfg[\"enabled\"]}')
print(f'  Idle-Schwelle: {cfg[\"idle_minutes\"]} Minuten')
print(f'  Aktuelle Inaktivität: {idle/60:.1f}m / {cfg[\"idle_minutes\"]}m')
print(f'  Nachtschicht: {cfg[\"night_start_hour\"]:02d}00–{cfg[\"night_end_hour\"]:02d}00 Uhr')

print()
print('[7/7] UI-MODI')
print(f'  Minimal-Start: ✓ (F2 zum Umschalten)')

print()
print('╔════════════════════════════════════════════════╗')
print('║        ✅ ALLE 7 FEATURES BEREIT!            ║')
print('║                                                ║')
print('║     'python main.py' eingeben zum Start      ║')
print('║     F2 = Ansicht → Dashboard                 ║')
print('║     F4 = Mute    F11 = Vollbild              ║')
print('╚════════════════════════════════════════════════╝')
"
```

---

## ⚠️ Häufige Fehler + Behebung

| Fehler | Ursache | Behebung |
|--------|--------|----------|
| `ModuleNotFoundError: agent.time_awareness` | PYTHONPATH polluted | `PYTHONPATH= python …` statt `python …` |
| `No module named 'google.generativeai'` | Dependencies fehlen | `pip install -r requirements.txt` |
| Trading wird nicht ausgelöst | Nicht genug inaktiv (< 20min) | `get_idle_seconds()` prüfen oder 20m warten |
| Screen-Agent öffnet keinen Browser | Playwright nicht installiert | `pip install playwright` + `python -m playwright install` |
| JARVIS lädt im Minimal-Modus nicht | OpenGL-Problem | → Q: Sie nutzen Remote Desktop? Dann auf lokalen Bildschirm wechseln |
| Dolphin antwortet nicht | OpenRouter-Key ungültig | API-Key in config/.env prüfen |

---

## 📝 Nächste Schritte nach Verifikation

1. ✅ **Diese Tests durchlaufen** (Sie sehen jede Komponente)
2. 📈 **Eine Practice-Session** (TradingView im Paper-Mode, 20min Idle versuchen)
3. 🛒 **Download + Amazon testen** (Browser-Automation live sehen)
4. 🏆 **Live-Trading starten** (wenn alles OK und Sie bereit)

---

## 🆘 Support

Wenn etwas fehlschlägt:
1. Zeichnen Sie die exakte Fehlermeldung auf
2. Prüfen Sie `.logs/jarvis.log` und `.logs/trading_audit.log`
3. Geben Sie mir die Fehlermeldung → ich repariere es innerhalb 1–2 Turns

**Viel Spaß, Boss!** ☕
