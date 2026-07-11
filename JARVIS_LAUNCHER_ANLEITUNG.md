# 🤖 JARVIS MASTER LAUNCHER — ANLEITUNG

## Schnellstart

**Einfach diese Datei doppelklicken:**

```
E:\Mark-XXXIX-main\JARVIS.bat
```

Das wars! JARVIS startet mit interaktivem Menü.

---

## 📋 HAUPTMENÜ

```
================================================================================
 HAUPTMENU
================================================================================

 1. Trading (Autonomous Trading aktivieren/steuern)
 2. Download (Anwendungen herunterladen und installieren)
 3. Research (Web-Recherche durchführen)
 4. Bildschirm (Screenshot-Analyse)
 5. Status (System-Überwachung und Logs)
 6. Einstellungen (Konfiguration, API-Keys, etc.)
 7. Sprachbefehl (Interaktive Sprachsteuerung)
 0. Beenden
```

---

## 🎮 MENÜS IM DETAIL

### 1️⃣ TRADING
- **Starten**: Autonomous Trading aktivieren (Background)
- **Manueller Trade**: BTC, ETH, etc. direkt handeln
- **Überwachung**: TradingMonitor-Agent starten
- **Alle Trades**: Liste aller ausgeführten Trades
- **Deaktivieren**: Trading Safety Mode

```
Eingabe Beispiel:
> 2
> Symbol: BTC
> Seite: BUY
> Menge: 0.5
> Preis: 45000
```

### 2️⃣ DOWNLOAD
- Beliebte Apps automatisch herunterladen
- Offizielle Quellen (blender.org, python.org, etc.)
- Auto-Installation optional

```
Available:
- blender (3D-Modellierung)
- python (Programmiersprache)
- git (Versionskontrolle)
- vscode (Code-Editor)
- nodejs (JavaScript)
- firefox (Browser)
```

### 3️⃣ WEB-RECHERCHE
- Multi-Source Google Search
- Zusammenfassungen
- Top 5 Ergebnisse anzeigen

```
> Recherchiere nach: Kubernetes Architecture
> [+] 5 Ergebnisse gefunden
```

### 4️⃣ BILDSCHIRM-ANALYSE
- Screenshot machen
- Windows erkennen
- OCR Text-Extraktion
- Vision-basierte Analyse

### 5️⃣ STATUS
- JARVIS-Zustand prüfen
- Logs anzeigen
- System-Info

### 6️⃣ EINSTELLUNGEN
- API-Keys prüfen (.env)
- State zurücksetzen
- Logs löschen
- Konfigurieren

### 7️⃣ SPRACHBEFEHL
- Interaktive Befehlseingabe
- "quit" zum Beenden

```
>> Trading bitcoin
[+] Befehl ausgeführt

>> Lade Blender herunter
[+] Download gestartet

>> quit
[+] Auf Wiedersehen, Boss!
```

---

## ⚙️ VORAUSSETZUNGEN

```
✓ Python 3.11+
✓ pip installiert
✓ .env mit API-Keys:
  - OPENAI_API_KEY
  - COMPOSIO_API_KEY
  - GEMINI_API_KEY
```

Fehlende Module werden automatisch installiert.

---

## 🚀 ERSTE SCHRITTE

1. **Starte JARVIS.bat**
   ```
   E:\Mark-XXXIX-main> JARVIS.bat
   ```

2. **Wähle ein Menü**
   ```
   Deine Wahl (0-7): 1
   ```

3. **Folge den Anweisungen**
   - Eingaben machen
   - Enter drücken
   - Ergebnisse sehen

4. **Zurück zum Menü**
   - Eingabe eingeben oder Taste drücken
   - Obermenü automatisch angezeigt

---

## 🔥 BELIEBTE BEFEHLE

### Trading
```
Menü 1 → 2 → BTC, BUY, 0.5, 45000
→ ✓ Trade buy 0.5x BTC AUSGEFÜHRT
```

### Download
```
Menü 2 → blender
→ ✓ Download erfolgreich
```

### Recherche
```
Menü 3 → Kubernetes
→ [+] 5 Ergebnisse gefunden
```

### Screenshot
```
Menü 4 → 1
→ ✓ Screenshot erfasst
```

### Sprachbefehl
```
Menü 7
>> Trading ethereum
→ [+] Befehl ausgeführt
```

---

## 📊 LOGS UND DATEN

```
E:\Mark-XXXIX-main\
├── .logs/          ← Alle Aktivitäten
├── .data/          ← State, Konfiguration
├── .env            ← API-Keys (NICHT versenden!)
└── JARVIS.bat      ← Diese Launcher
```

---

## ⚠️ WICHTIG

### Autonomous Trading
- **DEMO-MODE**: Keine echten Trades (noch)
- **LIVE-MODE**: Vor echter Integration Keys checken
- **SAFETY**: Können jederzeit deaktiviert werden

### API-Keys
- **Nicht committen** (.env in .gitignore)
- **Sicher lagern** (nur lokal)
- **Regelmäßig rotieren**

---

## 🛠️ FEHLERBEHANDLUNG

| Problem | Lösung |
|---------|--------|
| Python nicht gefunden | Install Python 3.11+ von python.org |
| .env fehlt | Erstelle .env mit API-Keys |
| Module fehlen | Werden automatisch via pip installiert |
| Trading nicht aktiv | Menü 6 → Einstellungen → API-Keys checken |

---

## 📞 SUPPORT

Wenn etwas nicht funktioniert:

1. Prüfe Logs: `.logs/`
2. Prüfe .env: API-Keys vorhanden?
3. Prüfe Python: `python --version`
4. Starte neu: `JARVIS.bat` erneut starten

---

**Boss, JARVIS ist einsatzbereit.**

Einfach `JARVIS.bat` starten und vollständig mit dem Menü arbeiten — alles in einer Datei.

🚀 Viel Erfolg!
