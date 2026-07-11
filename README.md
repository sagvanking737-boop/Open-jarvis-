# MARK XXXIX

MARK XXXIX is a local JARVIS-style desktop assistant with real-time voice,
screen awareness, tool use, Playwright browser automation, and a PyQt interface.

## Open Source Notice

Before publishing this repository publicly, review the project name, UI, docs,
and assets for third-party trademark or copyright conflicts. If you intend a
fully independent open-source project, use original branding and avoid implying
affiliation with any existing entertainment franchise or rights holder.

## Features

- Real-time voice interaction with Gemini Live
- Desktop and browser control
- Screen and file analysis
- YouTube playback via Playwright
- Amazon cart automation via Playwright
- TradingView analysis with paper-trading safety controls
- Optional Composio integrations for apps like Gmail, Calendar, GitHub, and Spotify

## Requirements

- Windows 10/11, macOS, or Linux
- Python 3.11 or 3.12
- Microphone
- Gemini API key
- Optional: OpenRouter API key
- Optional: Composio API key

## Setup

Clone the repository:

```bash
git clone https://github.com/YOUR_USERNAME/Mark-XXXIX.git
cd Mark-XXXIX
```

Install dependencies:

```bash
python -m pip install -r requirements.txt
python -m playwright install chromium
```

Create your local API key config:

```bash
python setup_keys.py
```

Start MARK XXXIX:

```bash
python main.py
```

On Windows you can also run:

```bat
start_mark.bat
```

Use `start_mark.bat` as the supported Windows launcher for the Live interface.

## Voice commands

- `Zeige mir die Erde` opens the interactive 3-D hologram and moves JARVIS into
  the presentation corner.
- `Fokussiere Erde` zooms the model and asks JARVIS to explain the subject.
- `Zeige Iron Man Mark XXXIX` renders any supported Mark from I to LXXXV;
  `Zeige alle Iron Man Anzuege` opens the full 85-suit armory catalog.
- `Zeige den Arc-Reaktor im Detail` starts an exploded component animation.
- `Programmiere eine Wetter-App` first checks whether VS Code is open, reuses
  or starts it, then begins the project workflow in `Desktop/JarvisProjects`.

## Background gesture camera

When the 3-D presentation is visible, JARVIS opens the configured camera only
for local MediaPipe hand tracking. No preview is shown and no frame is saved or
uploaded. Point with the index finger to move the HUD cursor. Pinch thumb and
index finger for click/drag, including rotating a model. Hold up index and
middle finger in a V shape, then spread or close them to zoom. Closing the 3-D
presentation releases the camera immediately.

Set `gesture_camera_enabled` to `false` in `config/api_keys.json`, or set the
environment variable `JARVIS_GESTURE_CAMERA=0`, to disable gesture input.

## API Keys

Do not commit real API keys.

This repository includes:

- `.env.example`
- `config/api_keys.example.json`

Your real local files are ignored by Git:

- `.env`
- `config/api_keys.json`

Each user must create their own local config with their own API keys.

## Composio

Composio is optional. If you want Gmail, Calendar, GitHub, Spotify, or similar
app integrations, add your own Composio API key with:

```bash
python setup_keys.py
```

Then connect apps in Composio according to their dashboard or CLI instructions.

If the Composio key is missing or invalid, MARK will not expose Composio tools
to the voice model.

## Trading Safety

TradingView automation is configured for paper-trading safety by default.
Review `config/trading.json` before enabling any trading workflow.

Freqtrade is bundled under `integrations/freqtrade` with `dry_run=true` enforced
by its launcher and JARVIS bridge. Run `integrations/freqtrade/setup.ps1` once,
then say `starte Freqtrade Dry-Run`. Live orders are not exposed by JARVIS.

## Obsidian Memory

JARVIS mirrors long-term memory to the configured Obsidian note in
`config/obsidian.json`. The camera feed and secrets are never written there.

Structured knowledge is stored under `Memory/User`, `Memory/Preferences`,
`Projects`, `Tasks`, `Errors`, `Solutions`, `Browser Sessions`, and
`System Documentation`. Every entry carries time, source, category, and status.
Secrets are redacted before writing. Use `obsidian_brain` to search old errors,
tasks, solutions, and interrupted browser work.

Hand tracking offers visible `diagnose` and `calibrate` modes. These modes draw
landmarks, confidence, FPS, brightness, gesture, and status locally while system
actions remain disabled. Runtime clicks require repeated stable detections.

Critical actions use exact confirmation phrases. Vague confirmations never pass.
Live trading is permanently blocked; Freqtrade and TradingView remain simulation-only.

## Voice Interruption

Full-duplex barge-in is enabled in `config/audio.json`. While JARVIS speaks, the
microphone remains active behind a local RMS echo gate. Stable user speech triggers
Gemini Live interruption; queued speech is discarded immediately so the new request
can be processed. Increase `barge_in_rms_threshold` if speaker echo causes false stops.

## Original GLB Viewer

Downloaded Iron Man suits, arc reactor, and Bugatti models use their complete
source meshes in a native OpenGL viewer. Smooth GPU shading replaces the reduced
triangle painter; no wireframe or triangle overlay is shown.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).

See [OPEN_SOURCE_RELEASE.md](OPEN_SOURCE_RELEASE.md) before publishing a public
repository.
