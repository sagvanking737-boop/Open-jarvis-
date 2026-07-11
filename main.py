import asyncio
import re
import threading
import json
import sys
import traceback
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import sounddevice as sd
from google import genai
from google.genai import types
from ui import JarvisUI
from agent.error_recovery import ErrorRecovery
from agent.safety_gate import check as check_safety
from agent.barge_in import BargeInGate, load_barge_in_settings
from memory.memory_manager import (
    load_memory, update_memory, format_memory_for_prompt,
)
from memory.obsidian_brain import (
    load_browser_state, record, record_error, start_self_diagnosis_watcher,
)

from actions.file_processor import file_processor
from actions.flight_finder     import flight_finder
from actions.open_app          import open_app
from actions.weather_report    import weather_action
from actions.send_message      import send_message
from actions.reminder          import reminder
from actions.computer_settings import computer_settings
from actions.screen_processor  import screen_process
from actions.youtube_video     import youtube_video, parse_youtube_command
from actions.desktop           import desktop_control
from actions.browser_control   import browser_control
from actions.file_controller   import file_controller
from actions.code_helper       import code_helper
from actions.dev_agent         import dev_agent
from actions.programming_workflow import programming_workflow
from actions.web_search        import web_search as web_search_action
from actions.computer_control  import computer_control
from actions.game_updater      import game_updater
from actions.system_info       import system_info
from actions.process_manager   import process_manager
from actions.network_manager   import network_manager
from actions.power_manager     import power_manager
from actions.credential_manager import credential_manager
from actions.phone_control     import handle_phone_control
from actions.download_assistant import download_assistant
from actions.amazon_shopper    import amazon_shopper
from actions.obsidian_brain    import obsidian_brain
from actions.gesture_diagnostics import gesture_diagnostics
from actions.focus_mode        import daddys_home_mode, is_daddys_home_phrase
from actions.world_news        import (
    format_news_for_speech,
    get_country_news,
    is_world_news_trigger,
)
from agent.auto_trader         import auto_trader_tool, start_trading_watcher
from agent.time_awareness      import (
    get_time_context, get_greeting_instruction, get_datetime_tool,
)
from agent.self_awareness      import build_self_knowledge, read_own_code
from agent.ironman_catalog     import is_arc_reactor_detail_request
from config.settings           import get_live_voice_name

# ─── Multi-Agent System ───────────────────────────────────────────────────────
try:
    from agent.swarm           import get_swarm
    from agent.composio_bridge import get_bridge
    _SWARM_AVAILABLE = True
except Exception as _e:
    print(f"[JARVIS] ⚠️ Multi-Agent-System nicht verfügbar: {_e}")
    _SWARM_AVAILABLE = False

# ─── Error Recovery System ─────────────────────────────────────────────────────
_recovery_engine = ErrorRecovery()
_COMPOSIO_ACTION_NAME = "composio_action"


def get_base_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent


BASE_DIR        = get_base_dir()
API_CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"
PROMPT_PATH     = BASE_DIR / "core" / "prompt.txt"
LIVE_MODEL          = "models/gemini-2.5-flash-native-audio-preview-12-2025"
CHANNELS            = 1
SEND_SAMPLE_RATE    = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE          = 1024

_COMPOSIO_TOOLS_MAP = {}
_COMPOSIO_DECLARATIONS = []

def load_native_composio_tools(genai_client):
    global _COMPOSIO_TOOLS_MAP, _COMPOSIO_DECLARATIONS
    try:
        from agent.composio_bridge import get_bridge
        bridge = get_bridge()
        if not bridge.is_configured:
            return
            
        native_apps = []
        if API_CONFIG_PATH.exists():
            with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                native_apps = data.get("composio_native_apps", [])
                
        if not native_apps:
            connected = bridge.list_connected_apps()
            native_apps = connected[:2]
            
        if not native_apps:
            return
            
        print(f"[JARVIS] 🔌 Lade native Composio-Tools für: {native_apps}")
        from composio import Composio
        from composio_gemini import GeminiProvider
        
        composio_client = Composio(api_key=bridge._key, provider=GeminiProvider(), dangerously_skip_version_check=True)
        composio_tools = composio_client.tools.get(user_id="default", toolkits=native_apps)
        
        count = 0
        for f in composio_tools:
            name = getattr(f, "__name__", None)
            if name:
                try:
                    # Convert to Gemini FunctionDeclaration
                    decl = types.FunctionDeclaration.from_callable(client=genai_client, callable=f)
                    _COMPOSIO_TOOLS_MAP[name] = f
                    _COMPOSIO_DECLARATIONS.append(decl)
                    count += 1
                except Exception as e:
                    print(f"[JARVIS] ⚠️ Überspringe native Composio-Aktion {name} wegen Fehler: {e}")
                
        print(f"[JARVIS] ✅ {count} native Composio-Tools erfolgreich geladen.")
    except Exception as e:
        print(f"[JARVIS] ⚠️ Fehler beim Laden der nativen Composio-Tools: {e}")

def _get_api_key() -> str:
    with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["gemini_api_key"]


def _load_system_prompt() -> str:
    try:
        return PROMPT_PATH.read_text(encoding="utf-8")
    except Exception:
        return (
            "You are JARVIS, Tony Stark's AI assistant. "
            "Be concise, direct, and always use the provided tools to complete tasks. "
            "Never simulate or guess results — always call the appropriate tool."
        )

_CTRL_RE = re.compile(r"<ctrl\d+>", re.IGNORECASE)

def _clean_transcript(text: str) -> str:    
    text = _CTRL_RE.sub("", text)
    text = re.sub(r"[\x00-\x08\x0b-\x1f]", "", text)
    return text.strip()

TOOL_DECLARATIONS = [
    {
        "name": "open_app",
        "description": (
            "Opens any application on the computer. "
            "Use this whenever the user asks to open, launch, or start any app, "
            "website, or program. Always call this tool — never just say you opened it."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "app_name": {
                    "type": "STRING",
                    "description": "Exact name of the application (e.g. 'WhatsApp', 'Chrome', 'Spotify')"
                }
            },
            "required": ["app_name"]
        }
    },
    {
        "name": "phone_control",
        "description": (
            "Controls the user's Android phone via ADB. "
            "Use this for any mobile phone control requests: checking battery status/info, "
            "launching apps (WhatsApp, Spotify, YouTube, Camera, Settings, Chrome), "
            "clicking coordinates, typing text, pressing buttons (Home, Back, Power, VolUp, VolDown, Apps), "
            "or taking a phone screenshot. "
            "USB-Debugging must be enabled on the phone."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "Action to perform: 'info' | 'launch' | 'key' | 'tap' | 'type' | 'screenshot'"
                },
                "app_name": {
                    "type": "STRING",
                    "description": "For 'launch' action: Name of the app or package (e.g. 'whatsapp', 'kamera', 'spotify')"
                },
                "key_name": {
                    "type": "STRING",
                    "description": "For 'key' action: Name of the key (e.g. 'home', 'back', 'power', 'volup', 'voldown', 'app_switch')"
                },
                "x": {
                    "type": "INTEGER",
                    "description": "For 'tap' action: X coordinate"
                },
                "y": {
                    "type": "INTEGER",
                    "description": "For 'tap' action: Y coordinate"
                },
                "text": {
                    "type": "STRING",
                    "description": "For 'type' action: The text string to type into the active text field on the phone"
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "web_search",
        "description": "Searches the web for any information.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query":  {"type": "STRING", "description": "Search query"},
                "mode":   {"type": "STRING", "description": "search (default) or compare"},
                "items":  {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Items to compare"},
                "aspect": {"type": "STRING", "description": "price | specs | reviews"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "weather_report",
        "description": "Gives the weather report to user",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "city": {"type": "STRING", "description": "City name"}
            },
            "required": ["city"]
        }
    },
    {
        "name": "send_message",
        "description": "Sends a text message via WhatsApp, Telegram, or other messaging platform.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "receiver":     {"type": "STRING", "description": "Recipient contact name"},
                "message_text": {"type": "STRING", "description": "The message to send"},
                "platform":     {"type": "STRING", "description": "Platform: WhatsApp, Telegram, etc."}
            },
            "required": ["receiver", "message_text", "platform"]
        }
    },
    {
        "name": "reminder",
        "description": "Sets a timed reminder using Task Scheduler.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "date":    {"type": "STRING", "description": "Date in YYYY-MM-DD format"},
                "time":    {"type": "STRING", "description": "Time in HH:MM format (24h)"},
                "message": {"type": "STRING", "description": "Reminder message text"}
            },
            "required": ["date", "time", "message"]
        }
    },
    {
        "name": "youtube_video",
        "description": (
            "Controls YouTube. Use for: playing videos, summarizing a video's content, "
            "getting video info, or showing trending videos. German commands like "
            "'spiele <song/video>' or 'spiel <song/video>' must use action=play and query=<song/video>. "
            "'spiele das neuste video von <channel>' must use action=play_latest and channel=<channel>. "
            "The play and play_latest actions use visible Playwright browser automation."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "play | play_latest | summarize | get_info | trending (default: play)"},
                "query":  {"type": "STRING", "description": "Search query for play action"},
                "channel": {"type": "STRING", "description": "Channel name or handle for play_latest action"},
                "save":   {"type": "BOOLEAN", "description": "Save summary to Notepad (summarize only)"},
                "region": {"type": "STRING", "description": "Country code for trending e.g. TR, US"},
                "url":    {"type": "STRING", "description": "Video URL for get_info action"},
            },
            "required": []
        }
    },
    {
        "name": "screen_process",
        "description": (
            "Captures and analyzes the screen, webcam, or mobile phone image. "
            "MUST be called when user asks what is on screen, what you see, "
            "analyze my screen, look at camera, what's on my phone, look at my phone screen, etc. "
            "You have NO visual ability without this tool. "
            "After calling this tool, stay SILENT — the vision module speaks directly."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "angle": {"type": "STRING", "description": "'screen' to capture display, 'camera' for webcam, or 'phone' to capture the user's mobile phone screen. Default: 'screen'"},
                "text":  {"type": "STRING", "description": "The question or instruction about the captured image"}
            },
            "required": ["text"]
        }
    },
    {
        "name": "computer_settings",
        "description": (
            "Controls the computer: volume, brightness, window management, keyboard shortcuts, "
            "typing text on screen, closing apps, fullscreen, dark mode, WiFi, restart, shutdown, "
            "scrolling, tab management, zoom, screenshots, lock screen, refresh/reload page. "
            "Use for ANY single computer control command. NEVER route to agent_task."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "The action to perform"},
                "description": {"type": "STRING", "description": "Natural language description of what to do"},
                "value":       {"type": "STRING", "description": "Optional value: volume level, text to type, etc."}
            },
            "required": []
        }
    },
    {
        "name": "browser_control",
        "description": (
            "Controls any web browser. Use for: opening websites, searching the web, "
            "clicking elements, filling forms, scrolling, screenshots, navigation, any web-based task. "
            "Always pass the 'browser' parameter when the user specifies a browser (e.g. 'open in Edge', "
            "'use Firefox', 'open Chrome'). Multiple browsers can run simultaneously."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "go_to | search | click | type | scroll | fill_form | smart_click | smart_type | get_text | get_url | press | new_tab | close_tab | screenshot | back | forward | reload | switch | list_browsers | close | close_all"},
                "browser":     {"type": "STRING", "description": "Target browser: chrome | edge | firefox | opera | operagx | brave | vivaldi | safari. Omit to use the currently active browser."},
                "url":         {"type": "STRING", "description": "URL for go_to / new_tab action"},
                "query":       {"type": "STRING", "description": "Search query for search action"},
                "engine":      {"type": "STRING", "description": "Search engine: google | bing | duckduckgo | yandex (default: google)"},
                "selector":    {"type": "STRING", "description": "CSS selector for click/type"},
                "text":        {"type": "STRING", "description": "Text to click or type"},
                "description": {"type": "STRING", "description": "Element description for smart_click/smart_type"},
                "direction":   {"type": "STRING", "description": "up | down for scroll"},
                "amount":      {"type": "INTEGER", "description": "Scroll amount in pixels (default: 500)"},
                "key":         {"type": "STRING", "description": "Key name for press action (e.g. Enter, Escape, F5)"},
                "path":        {"type": "STRING", "description": "Save path for screenshot"},
                "incognito":   {"type": "BOOLEAN", "description": "Open in private/incognito mode"},
                "clear_first": {"type": "BOOLEAN", "description": "Clear field before typing (default: true)"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "file_controller",
        "description": "Manages files and folders: list, create, delete, move, copy, rename, read, write, find, disk usage.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "list | create_file | create_folder | delete | move | copy | rename | read | write | find | largest | disk_usage | organize_desktop | info"},
                "path":        {"type": "STRING", "description": "File/folder path or shortcut: desktop, downloads, documents, home"},
                "destination": {"type": "STRING", "description": "Destination path for move/copy"},
                "new_name":    {"type": "STRING", "description": "New name for rename"},
                "content":     {"type": "STRING", "description": "Content for create_file/write"},
                "name":        {"type": "STRING", "description": "File name to search for"},
                "extension":   {"type": "STRING", "description": "File extension to search (e.g. .pdf)"},
                "count":       {"type": "INTEGER", "description": "Number of results for largest"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "desktop_control",
        "description": "Controls the desktop: wallpaper, organize, clean, list, stats.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "wallpaper | wallpaper_url | organize | clean | list | stats | task"},
                "path":   {"type": "STRING", "description": "Image path for wallpaper"},
                "url":    {"type": "STRING", "description": "Image URL for wallpaper_url"},
                "mode":   {"type": "STRING", "description": "by_type or by_date for organize"},
                "task":   {"type": "STRING", "description": "Natural language desktop task"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "code_helper",
        "description": "Writes, edits, explains, runs, or builds code files.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "write | edit | explain | run | build | auto (default: auto)"},
                "description": {"type": "STRING", "description": "What the code should do or what change to make"},
                "language":    {"type": "STRING", "description": "Programming language (default: python)"},
                "output_path": {"type": "STRING", "description": "Where to save the file"},
                "file_path":   {"type": "STRING", "description": "Path to existing file for edit/explain/run/build"},
                "code":        {"type": "STRING", "description": "Raw code string for explain"},
                "args":        {"type": "STRING", "description": "CLI arguments for run/build"},
                "timeout":     {"type": "INTEGER", "description": "Execution timeout in seconds (default: 30)"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "dev_agent",
        "description": "Builds complete multi-file projects from scratch: plans, writes files, installs deps, opens VSCode, runs and fixes errors.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "description":  {"type": "STRING", "description": "What the project should do"},
                "language":     {"type": "STRING", "description": "Programming language (default: python)"},
                "project_name": {"type": "STRING", "description": "Optional project folder name"},
                "timeout":      {"type": "INTEGER", "description": "Run timeout in seconds (default: 30)"},
            },
            "required": ["description"]
        }
    },
    {
        "name": "programming_workflow",
        "description": (
            "Mandatory workflow for the German command 'programmiere ...'. It first checks whether "
            "Visual Studio Code is running, reuses it if it is, otherwise opens VS Code, and only then "
            "starts a new multi-file coding project in the dedicated JarvisProjects directory. "
            "Use this instead of code_helper or dev_agent whenever the user says 'programmiere'."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "description": {"type": "STRING", "description": "What the program or feature should do"},
                "language": {"type": "STRING", "description": "Programming language, default python"},
                "project_name": {"type": "STRING", "description": "Optional project folder name below Desktop/JarvisProjects"},
                "workspace": {"type": "STRING", "description": "Optional existing project folder below Desktop/JarvisProjects"},
                "timeout": {"type": "INTEGER", "description": "Run timeout in seconds, default 30"}
            },
            "required": ["description"]
        }
    },
    {
        "name": "agent_task",
        "description": (
            "Executes complex multi-step tasks requiring multiple different tools. "
            "Examples: 'research X and save to file', 'find and organize files'. "
            "DO NOT use for single commands. NEVER use for Steam/Epic — use game_updater."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "goal":     {"type": "STRING", "description": "Complete description of what to accomplish"},
                "priority": {"type": "STRING", "description": "low | normal | high (default: normal)"},
                "context":  {"type": "STRING", "description": "Important constraints, prior decisions, files, or success criteria"},
                "max_steps": {"type": "INTEGER", "description": "Planning budget from 1 to 12 steps (default 12 for large tasks)"}
            },
            "required": ["goal"]
        }
    },
    {
        "name": "swarm_task",
        "description": (
            "Activates the 60-agent multi-specialist swarm for complex questions, deep analysis, "
            "comparisons, or topics where multiple expert perspectives add value. "
            "Complex questions are routed through OpenRouter openai/gpt-oss-20b:free for Jarvis synthesis. "
            "Use for: in-depth research, strategy advice, technical analysis, opinion questions, "
            "'what do you think about X?', 'which is better X or Y?', complex planning. "
            "NOT needed for simple factual lookups or single-tool tasks."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query":      {"type": "STRING",  "description": "The question or task for the agent swarm"},
                "max_agents": {"type": "INTEGER", "description": "Max agents to activate (1-60, default: 5)"},
                "context":    {"type": "STRING",  "description": "Additional context from the conversation"},
            },
            "required": ["query"]
        }
    },
    {
        "name": "composio_action",
        "description": (
            "Connects to 1000+ real apps and services via Composio: Gmail, GitHub, Slack, Notion, "
            "Google Calendar, Google Drive, Google Sheets, Trello, Jira, Discord, Twitter/X, "
            "LinkedIn, Spotify, YouTube, Stripe, HubSpot, Dropbox, Zoom, Figma, Asana, and many more. "
            "Use for real actions in these apps: send emails, create GitHub issues, post Slack messages, "
            "add calendar events, create Notion pages, manage spreadsheets, etc."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "task":    {"type": "STRING", "description": "Natural language description of what to do in the app"},
                "app":     {"type": "STRING", "description": "Target app name (e.g. gmail, github, slack, notion, googlecalendar)"},
                "action":  {"type": "STRING", "description": "Specific action name if known (e.g. GMAIL_SEND_EMAIL)"},
                "params":  {"type": "STRING", "description": "JSON string of action parameters if known"},
            },
            "required": ["task"]
        }
    },
    {
        "name": "computer_control",
        "description": "Direct computer control: type, click, hotkeys, scroll, move mouse, screenshots, find elements on screen.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "type | smart_type | click | double_click | right_click | hotkey | press | scroll | move | copy | paste | screenshot | wait | clear_field | focus_window | screen_find | screen_click | random_data | user_data"},
                "text":        {"type": "STRING", "description": "Text to type or paste"},
                "x":           {"type": "INTEGER", "description": "X coordinate"},
                "y":           {"type": "INTEGER", "description": "Y coordinate"},
                "keys":        {"type": "STRING", "description": "Key combination e.g. 'ctrl+c'"},
                "key":         {"type": "STRING", "description": "Single key e.g. 'enter'"},
                "direction":   {"type": "STRING", "description": "up | down | left | right"},
                "amount":      {"type": "INTEGER", "description": "Scroll amount (default: 3)"},
                "seconds":     {"type": "NUMBER",  "description": "Seconds to wait"},
                "title":       {"type": "STRING",  "description": "Window title for focus_window"},
                "description": {"type": "STRING",  "description": "Element description for screen_find/screen_click"},
                "type":        {"type": "STRING",  "description": "Data type for random_data"},
                "field":       {"type": "STRING",  "description": "Field for user_data: name|email|city"},
                "clear_first": {"type": "BOOLEAN", "description": "Clear field before typing (default: true)"},
                "path":        {"type": "STRING",  "description": "Save path for screenshot"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "game_updater",
        "description": (
            "THE ONLY tool for ANY Steam or Epic Games request. "
            "Use for: installing, downloading, updating games, listing installed games, "
            "checking download status, scheduling updates. "
            "ALWAYS call directly for any Steam/Epic/game request. "
            "NEVER use agent_task, browser_control, or web_search for Steam/Epic."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":    {"type": "STRING",  "description": "update | install | list | download_status | schedule | cancel_schedule | schedule_status (default: update)"},
                "platform":  {"type": "STRING",  "description": "steam | epic | both (default: both)"},
                "game_name": {"type": "STRING",  "description": "Game name (partial match supported)"},
                "app_id":    {"type": "STRING",  "description": "Steam AppID for install (optional)"},
                "hour":      {"type": "INTEGER", "description": "Hour for scheduled update 0-23 (default: 3)"},
                "minute":    {"type": "INTEGER", "description": "Minute for scheduled update 0-59 (default: 0)"},
                "shutdown_when_done": {"type": "BOOLEAN", "description": "Shut down PC when download finishes"},
            },
            "required": []
        }
    },
    {
        "name": "flight_finder",
        "description": "Searches Google Flights and speaks the best options.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "origin":      {"type": "STRING",  "description": "Departure city or airport code"},
                "destination": {"type": "STRING",  "description": "Arrival city or airport code"},
                "date":        {"type": "STRING",  "description": "Departure date (any format)"},
                "return_date": {"type": "STRING",  "description": "Return date for round trips"},
                "passengers":  {"type": "INTEGER", "description": "Number of passengers (default: 1)"},
                "cabin":       {"type": "STRING",  "description": "economy | premium | business | first"},
                "save":        {"type": "BOOLEAN", "description": "Save results to Notepad"},
            },
            "required": ["origin", "destination", "date"]
        }
    },
    {
        "name": "shutdown_jarvis",
        "description": (
            "Shuts down the assistant completely. "
            "Call this when the user expresses intent to end the conversation, "
            "close the assistant, say goodbye, or stop Jarvis. "
            "The user can say this in ANY language."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {},
        }
    },
    {
    "name": "file_processor",
    "description": (
        "Processes any file that the user has uploaded or dropped onto the interface. "
        "Use this when the user refers to an uploaded file and wants an action on it. "
        "Supports: images (describe/ocr/resize/compress/convert), "
        "PDFs (summarize/extract_text/to_word), "
        "Word docs & text files (summarize/fix/reformat/translate), "
        "CSV/Excel (analyze/stats/filter/sort/convert), "
        "JSON/XML (validate/format/analyze), "
        "code files (explain/review/fix/optimize/run/document/test), "
        "audio (transcribe/trim/convert/info), "
        "video (trim/extract_audio/extract_frame/compress/transcribe/info), "
        "archives (list/extract), "
        "presentations (summarize/extract_text). "
        "ALWAYS call this tool when a file has been uploaded and the user gives a command about it. "
        "If the user's command is ambiguous, pick the most logical action for that file type."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "file_path": {
                "type": "STRING",
                "description": "Full path to the uploaded file. Leave empty to use the currently uploaded file."
            },
            "action": {
                "type": "STRING",
                "description": (
                    "What to do with the file. Examples by type:\n"
                    "image: describe | ocr | resize | compress | convert | info\n"
                    "pdf: summarize | extract_text | to_word | info\n"
                    "docx/txt: summarize | fix | reformat | translate_hint | word_count | to_bullet\n"
                    "csv/excel: analyze | stats | filter | sort | convert | info\n"
                    "json: validate | format | analyze | to_csv\n"
                    "code: explain | review | fix | optimize | run | document | test\n"
                    "audio: transcribe | trim | convert | info\n"
                    "video: trim | extract_audio | extract_frame | compress | transcribe | info | convert\n"
                    "archive: list | extract\n"
                    "pptx: summarize | extract_text | analyze"
                )
            },
            "instruction": {
                "type": "STRING",
                "description": "Free-form instruction if action doesn't cover it. E.g. 'translate this to Turkish', 'find all email addresses'"
            },
            "format": {
                "type": "STRING",
                "description": "Target format for conversion. E.g. 'mp3', 'pdf', 'csv', 'png'"
            },
            "width":     {"type": "INTEGER", "description": "Target width for image resize"},
            "height":    {"type": "INTEGER", "description": "Target height for image resize"},
            "scale":     {"type": "NUMBER",  "description": "Scale factor for image resize (e.g. 0.5)"},
            "quality":   {"type": "INTEGER", "description": "Quality 1-100 for image/video compress"},
            "start":     {"type": "STRING",  "description": "Start time for trim: seconds or HH:MM:SS"},
            "end":       {"type": "STRING",  "description": "End time for trim: seconds or HH:MM:SS"},
            "timestamp": {"type": "STRING",  "description": "Timestamp for video frame extraction HH:MM:SS"},
            "column":    {"type": "STRING",  "description": "Column name for CSV filter/sort"},
            "value":     {"type": "STRING",  "description": "Filter value for CSV filter"},
            "condition": {"type": "STRING",  "description": "Filter condition: equals|contains|gt|lt"},
            "ascending": {"type": "BOOLEAN", "description": "Sort order for CSV sort (default: true)"},
            "save":      {"type": "BOOLEAN", "description": "Save result to file (default: true)"},
            "destination": {"type": "STRING", "description": "Output folder for archive extract"},
        },
        "required": []
    }
},
    {
        "name": "save_memory",
        "description": (
            "Save an important personal fact about the user to long-term memory. "
            "Call this silently whenever the user reveals something worth remembering: "
            "name, age, city, job, preferences, hobbies, relationships, projects, or future plans. "
            "Do NOT call for: weather, reminders, searches, or one-time commands. "
            "Do NOT announce that you are saving — just call it silently. "
            "Values must be in English regardless of the conversation language."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "category": {
                    "type": "STRING",
                    "description": (
                        "identity — name, age, birthday, city, job, language, nationality | "
                        "preferences — favorite food/color/music/film/game/sport, hobbies | "
                        "projects — active projects, goals, things being built | "
                        "relationships — friends, family, partner, colleagues | "
                        "wishes — future plans, things to buy, travel dreams | "
                        "notes — habits, schedule, anything else worth remembering"
                    )
                },
                "key":   {"type": "STRING", "description": "Short snake_case key (e.g. name, favorite_food, sister_name)"},
                "value": {"type": "STRING", "description": "Concise value in English (e.g. Fatih, pizza, older sister)"},
            },
            "required": ["category", "key", "value"]
        }
    },
    {
        "name": "obsidian_brain",
        "description": (
            "Searches JARVIS structured Obsidian knowledge: previous errors, solutions, "
            "tasks, browser sessions, project history, and self-diagnosis."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "status | diagnose | search | errors | tasks | browser_resume | record_task | record"},
                "query": {"type": "STRING", "description": "Search text"},
                "category": {"type": "STRING", "description": "user | preferences | projects | tasks | errors | solutions | browser | system | decisions"},
                "title": {"type": "STRING", "description": "Task title"},
                "content": {"type": "STRING", "description": "Task details"},
                "status": {"type": "STRING", "description": "open | investigating | fixed | active"}
                ,"source": {"type": "STRING", "description": "conversation | browser | code | system"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "gesture_diagnostics",
        "description": "Runs visible local hand-camera diagnosis or safe calibration. No mouse actions are emitted during testing.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "diagnose | calibrate"},
                "camera_index": {"type": "INTEGER", "description": "Optional camera index"},
                "duration_seconds": {"type": "NUMBER", "description": "Diagnostic duration"},
                "show_preview": {"type": "BOOLEAN", "description": "Show local camera landmarks window"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "system_info",
        "description": "Gets system information (CPU, RAM, GPU, disk, battery, OS, uptime, installed/startup apps).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "cpu | ram | gpu | disk | battery | os_info | uptime | overview | installed_apps | startup_apps | add_startup | remove_startup"},
                "name": {"type": "STRING", "description": "App name for startup modification"},
                "path": {"type": "STRING", "description": "App path for add_startup"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "process_manager",
        "description": "Manages Windows processes and services.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "list | top | kill | kill_tree | find | services_list | service_start | service_stop | service_restart | service_status"},
                "name": {"type": "STRING", "description": "Process name or service name"},
                "pid": {"type": "INTEGER", "description": "Process ID"},
                "count": {"type": "INTEGER", "description": "Number of items to return for top"},
                "sort_by": {"type": "STRING", "description": "cpu | memory"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "network_manager",
        "description": "Manages network, WiFi, IPs, firewall, and runs speedtests.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "ip | ping | dns | speedtest | wifi_list | wifi_connect | wifi_disconnect | wifi_status | connections | adapters | firewall_status | firewall_toggle | hosts_list | flush_dns"},
                "host": {"type": "STRING", "description": "Target host for ping/dns"},
                "ssid": {"type": "STRING", "description": "WiFi SSID to connect to"},
                "password": {"type": "STRING", "description": "WiFi password"},
                "state": {"type": "STRING", "description": "on | off for firewall_toggle"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "power_manager",
        "description": "Controls power settings, sleep, hibernation, and screen timeouts.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "sleep | hibernate | power_plans | set_power_plan | active_plan | screen_timeout | sleep_timeout | caffeinate"},
                "plan": {"type": "STRING", "description": "Power plan name (e.g. balanced, high performance)"},
                "minutes": {"type": "INTEGER", "description": "Timeout in minutes"},
                "power_source": {"type": "STRING", "description": "ac | dc (default: ac)"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "credential_manager",
        "description": "Manages local vault, Windows credentials, and browser passwords.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "windows_credentials | browser_passwords | show_password | wifi_passwords | vault_store | vault_get | vault_list | vault_delete"},
                "browser": {"type": "STRING", "description": "chrome | edge | all"},
                "service": {"type": "STRING", "description": "Service name for vault/show_password"},
                "username": {"type": "STRING", "description": "Username to store"},
                "password": {"type": "STRING", "description": "Password to store"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "download_assistant",
        "description": (
            "Downloads a program/application from the internet using the visible browser "
            "with mouse control (screen UI agent). Use whenever the user says "
            "'downloade X', 'lade X herunter', 'installiere X', 'download X'. "
            "JARVIS opens the browser, finds the official installer link and downloads it."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "app_name": {"type": "STRING", "description": "Name of the program to download (e.g. 'blender', 'obs', 'vlc')"}
            },
            "required": ["app_name"]
        }
    },
    {
        "name": "amazon_shopper",
        "description": (
            "Searches Amazon for a product using the visible browser with mouse control "
            "and adds it to the shopping cart. Use whenever the user says "
            "'ich brauche X', 'bestelle X', 'such mir X auf Amazon', 'I need X'. "
            "Never buys automatically — cart only."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "product":     {"type": "STRING",  "description": "Product to search for (e.g. 'wireless gaming mouse')"},
                "add_to_cart": {"type": "BOOLEAN", "description": "Request cart action; still requires explicit confirmation"},
                "max_price":   {"type": "INTEGER", "description": "Optional price limit in euros"}
                ,"requirements": {"type": "STRING", "description": "Required size, features, delivery, or other preferences"}
                ,"requirements_confirmed": {"type": "BOOLEAN", "description": "True only after user answered requirement questions"}
                ,"selected_index": {"type": "INTEGER", "description": "Chosen result index, default 0"}
                ,"confirm_add_to_cart": {"type": "BOOLEAN", "description": "True only after explicit cart confirmation"}
                ,"confirmation_phrase": {"type": "STRING", "description": "Exact user confirmation phrase"}
                ,"warranty_choice": {"type": "STRING", "description": "Explicit warranty option or keine Garantie"}
            },
            "required": ["product"]
        }
    },
    {
        "name": "auto_trader",
            "description": (
                "Controls the autonomous TradingView trading system. "
                "JARVIS trades automatically via screen UI when the boss is idle for 20 minutes "
                "and all night (22:00-06:00) with a multi-model council. "
                "Default mode is TradingView Paper Trading; never use a real-money broker unless "
                "the local trading config explicitly enables live trading. "
                "Use for: 'trading status', 'starte trading', 'stoppe trading', 'trade jetzt', "
                "'scan charts', 'setze symbol auf X', 'setze trading watchlist auf X,Y', "
                "'Freqtrade Status', 'starte Freqtrade Dry-Run', 'stoppe Freqtrade'."
            ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "status | start | stop | scan | trade_now | set_symbol | set_watchlist | configure | freqtrade_status | freqtrade_start | freqtrade_stop"},
                "symbol": {"type": "STRING", "description": "Trading symbol for set_symbol (e.g. BINANCE:BTCUSDT, NASDAQ:NVDA)"},
                "symbols": {"type": "STRING", "description": "Comma-separated symbols for set_watchlist"},
                "max_symbols_per_scan": {"type": "INTEGER", "description": "How many watchlist charts to scan"},
                "min_confidence": {"type": "INTEGER", "description": "Minimum model confidence for a paper trade"},
                "trades_per_session_target": {"type": "INTEGER", "description": "Target paper trades per session"},
                "chart_interval": {"type": "STRING", "description": "TradingView interval, e.g. 5, 15, 60, D"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "get_datetime",
        "description": (
            "Returns the exact current date and time. Call when the user asks the time/date "
            "or when you need precise time for calculations after a long session."
        ),
        "parameters": {"type": "OBJECT", "properties": {}}
    },
    {
        "name": "read_own_code",
        "description": (
            "Reads JARVIS's own source code files. Call when the user asks how a part of you "
            "works, or when you need to debug yourself. Call without 'file' to list all files."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "file":  {"type": "STRING",  "description": "Relative path e.g. 'agent/screen_agent.py'. Empty = list files."},
                "start": {"type": "INTEGER", "description": "Start line (default 1)"},
                "lines": {"type": "INTEGER", "description": "Number of lines (default 200, max 300)"}
            },
            "required": []
        }
    },
    {
        "name": "ui_mode",
        "description": (
            "Switches the JARVIS interface between minimal mode (only the hologram face) "
            "and dashboard mode (3D model + all system information). "
            "Use when the user says 'zeig mir alles', 'dashboard', 'zeig mir die infos' (dashboard) "
            "or 'nur du', 'minimalansicht', 'mach dich klein', 'blende alles aus' (minimal)."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "minimal | dashboard | toggle"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "hologram_control",
        "description": (
            "Controls the dedicated 3-D hologram presentation. Use action=show when the user says "
            "'zeige/zeig mir <object or topic>' and they want a visual model, action=focus when the "
            "user says 'fokussiere/fokusire/fukusire <object or topic>', action=detail for 'im Detail', "
            "'zerlege', 'Explosionsansicht', or an Arc Reactor component animation, and action=hide to close it. "
            "After a focus call, explain the focused topic concisely in the user's language. Do not use "
            "this for dashboards, logs, files, or screen captures."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "show | focus | detail | hide"},
                "subject": {"type": "STRING", "description": "Object or topic for the 3-D hologram, e.g. all Iron Man suits, Iron Man Mark 39, Hulkbuster, Arc Reactor, Iron Man helmet, repulsor, Erde, Atom, DNA"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "world_news_globe",
        "description": (
            "Opens the interactive World Intel globe. Call this when the user asks "
            "'Was sind die Neuigkeiten von heute?', 'Was geht heute ab?', 'Weltnachrichten', "
            "or requests today's world news. Tell the user to click a country; JARVIS then "
            "loads and speaks that country's current headlines."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {},
            "required": []
        }
    }
]

for _tool in TOOL_DECLARATIONS:
    if _tool.get("name") in {
        "send_message", "download_assistant", "dev_agent", "programming_workflow",
        "code_helper", "file_controller", "browser_control",
    }:
        _properties = _tool.setdefault("parameters", {}).setdefault("properties", {})
        _properties["confirmation_phrase"] = {
            "type": "STRING",
            "description": "Exact explicit user confirmation for a critical action; never infer it",
        }

class JarvisLive:

    def __init__(self, ui: JarvisUI):
        self.ui             = ui
        self.session        = None
        self.audio_in_queue = None
        self.out_queue      = None
        self._loop          = None
        self._is_speaking   = False
        self._speaking_lock = threading.Lock()
        self.ui.on_text_command = self._on_text_command
        self.ui.on_voice_changed = self._on_voice_changed
        self.ui.on_country_selected = self._on_country_selected
        self._turn_done_event: asyncio.Event | None = None
        self._playback_interrupt_event: asyncio.Event | None = None
        self._greeted = False

    def _trigger_daddys_home_mode(self) -> bool:
        self.ui.write_log("SYS: Daddy's home mode activated.")
        threading.Thread(
            target=daddys_home_mode,
            kwargs={"player": self.ui, "speak": self.speak},
            daemon=True,
        ).start()
        return True

    def _trigger_youtube_action(self, params: dict) -> bool:
        action = params.get("action", "play")
        target = params.get("channel") or params.get("query") or ""
        self.ui.write_log(f"SYS: YouTube Playwright {action} -> {target}")
        threading.Thread(
            target=youtube_video,
            kwargs={"parameters": params, "player": self.ui},
            daemon=True,
        ).start()
        return True

    def _trigger_world_news_globe(self) -> bool:
        self.ui.control_model("show", "Welt-News")
        self.ui.set_news_status("Land anklicken - JARVIS laedt die aktuellen Meldungen")
        self.ui.write_log("SYS: World Intel globe opened.")
        return True

    def _on_country_selected(self, country_code: str):
        news_data = get_country_news(country_code)
        country = news_data.get("country_name", country_code)
        if news_data.get("success"):
            self.ui.set_news_status(
                f"{news_data.get('count', 0)} Meldungen fuer {country} geladen"
            )
            self.ui.write_log(f"SYS: World Intel headlines for {country}:")
            for item in news_data.get("news", [])[:5]:
                source = f" [{item.get('source')}]" if item.get("source") else ""
                self.ui.write_log(f"NEWS: {item.get('title', '')}{source}")
        else:
            self.ui.set_news_status(f"Keine Meldungen fuer {country} abrufbar")
            self.ui.write_log(f"ERR: World Intel {country}: {news_data.get('error', 'unknown')}")
        self.speak(format_news_for_speech(news_data))

    def _on_text_command(self, text: str):
        if is_world_news_trigger(text):
            self._trigger_world_news_globe()
            return
        if is_daddys_home_phrase(text):
            self._trigger_daddys_home_mode()
            return
        youtube_params = parse_youtube_command(text)
        if youtube_params:
            self._trigger_youtube_action(youtube_params)
            return
        if not self._loop or not self.session:
            return
        asyncio.run_coroutine_threadsafe(
            self.session.send_client_content(
                turns={"parts": [{"text": text}]},
                turn_complete=True
            ),
            self._loop
        )

    def _on_voice_changed(self, voice: str):
        self.ui.write_log(f"SYS: Voice {voice} saved. Restart or reconnect to apply.")

    def set_speaking(self, value: bool):
        with self._speaking_lock:
            self._is_speaking = value
        if value:
            self.ui.set_state("SPEAKING")
        elif not self.ui.muted:
            self.ui.set_state("LISTENING")

    def speak(self, text: str):
        if not self._loop or not self.session:
            return
        asyncio.run_coroutine_threadsafe(
            self.session.send_client_content(
                turns={"parts": [{"text": text}]},
                turn_complete=True
            ),
            self._loop
        )

    def speak_error(self, tool_name: str, error: str):
        short = str(error)[:120]
        try:
            record_error(tool_name, "tool execution", error, logs=traceback.format_exc())
        except Exception:
            pass
        self.ui.write_log(f"ERR: {tool_name} — {short}")
        self.speak(f"Sir, {tool_name} encountered an error. {short}")

    def _build_config(self) -> types.LiveConnectConfig:
        memory     = load_memory()
        mem_str    = format_memory_for_prompt(memory)
        sys_prompt = _load_system_prompt()
        voice_name = get_live_voice_name()
        audio_settings = load_barge_in_settings()

        parts = [get_time_context()]
        if mem_str:
            parts.append(mem_str)
        parts.append(sys_prompt)
        try:
            browser_state = load_browser_state()
            if browser_state and browser_state.get("status") in {
                "active", "interrupted", "waiting_confirmation"
            }:
                parts.append(
                    "[INTERRUPTED BROWSER TASK] Ask once whether the Boss wants to resume. "
                    "Never finish a purchase automatically. State: "
                    + json.dumps(browser_state, ensure_ascii=False)[:1800]
                )
        except Exception:
            pass
        try:
            parts.append(build_self_knowledge())
        except Exception as e:
            print(f"[JARVIS] ⚠️ Selbstkenntnis nicht verfügbar: {e}")

        all_funcs = list(TOOL_DECLARATIONS)
        if _SWARM_AVAILABLE:
            try:
                if get_bridge().is_configured:
                    all_funcs += _COMPOSIO_DECLARATIONS
                else:
                    all_funcs = [
                        f for f in all_funcs
                        if f.get("name") != _COMPOSIO_ACTION_NAME
                    ]
            except Exception:
                all_funcs = [
                    f for f in all_funcs
                    if f.get("name") != _COMPOSIO_ACTION_NAME
                ]
        else:
            all_funcs = [
                f for f in all_funcs
                if f.get("name") != _COMPOSIO_ACTION_NAME
            ]
        return types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            output_audio_transcription={},
            input_audio_transcription={},
            realtime_input_config=types.RealtimeInputConfig(
                automatic_activity_detection=types.AutomaticActivityDetection(
                    disabled=False,
                    start_of_speech_sensitivity=audio_settings["vad_start_sensitivity"],
                    end_of_speech_sensitivity=audio_settings["vad_end_sensitivity"],
                    prefix_padding_ms=int(audio_settings["vad_prefix_padding_ms"]),
                    silence_duration_ms=int(audio_settings["vad_silence_duration_ms"]),
                ),
                activity_handling=types.ActivityHandling.START_OF_ACTIVITY_INTERRUPTS,
                turn_coverage=types.TurnCoverage.TURN_INCLUDES_ONLY_ACTIVITY,
            ),
            system_instruction="\n".join(parts),
            tools=[{"function_declarations": all_funcs}],
            session_resumption=types.SessionResumptionConfig(),
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=voice_name
                    )
                )
            ),
        )

    async def _execute_tool(self, fc) -> types.FunctionResponse:
        name = fc.name
        args = dict(fc.args or {})

        print(f"[JARVIS] 🔧 {name}  {args}")
        self.ui.set_state("THINKING")

        if name == "save_memory":
            category = args.get("category", "notes")
            key      = args.get("key", "")
            value    = args.get("value", "")
            if key and value:
                update_memory({category: {key: {"value": value}}})
                print(f"[Memory] 💾 save_memory: {category}/{key} = {value}")
            if not self.ui.muted:
                self.ui.set_state("LISTENING")
            return types.FunctionResponse(
                id=fc.id, name=name,
                response={"result": "ok", "silent": True}
            )

        loop   = asyncio.get_event_loop()
        result = "Done."

        safety_allowed, safety_message = check_safety(name, args)
        if not safety_allowed:
            if not self.ui.muted:
                self.ui.set_state("LISTENING")
            return types.FunctionResponse(
                id=fc.id, name=name,
                response={"result": safety_message, "blocked": True},
            )

        try:
            if name in _COMPOSIO_TOOLS_MAP:
                # Verwende Error Recovery für Composio-Aktionen
                def execute_composio():
                    return get_bridge().execute_action(action_name=name, parameters=args)
                
                r = await loop.run_in_executor(
                    None,
                    lambda: _recovery_engine.execute_with_recovery(
                        execute_composio,
                        error_name=f"composio_{name}",
                        fallback_func=lambda: {"status": "skipped", "reason": "composio_error"}
                    )
                )
                result = r

            elif name == "open_app":
                r = await loop.run_in_executor(None, lambda: open_app(parameters=args, response=None, player=self.ui))
                result = r or f"Opened {args.get('app_name')}."

            elif name == "phone_control":
                r = await loop.run_in_executor(None, lambda: handle_phone_control(parameters=args, player=self.ui))
                result = r or "Done."

            elif name == "weather_report":
                r = await loop.run_in_executor(None, lambda: weather_action(parameters=args, player=self.ui))
                result = r or "Weather delivered."

            elif name == "browser_control":
                r = await loop.run_in_executor(None, lambda: browser_control(parameters=args, player=self.ui))
                result = r or "Done."

            elif name == "file_controller":
                r = await loop.run_in_executor(None, lambda: file_controller(parameters=args, player=self.ui))
                result = r or "Done."

            elif name == "send_message":
                r = await loop.run_in_executor(None, lambda: send_message(parameters=args, response=None, player=self.ui, session_memory=None))
                result = r or f"Message sent to {args.get('receiver')}."

            elif name == "reminder":
                r = await loop.run_in_executor(None, lambda: reminder(parameters=args, response=None, player=self.ui))
                result = r or "Reminder set."

            elif name == "youtube_video":
                r = await loop.run_in_executor(None, lambda: youtube_video(parameters=args, response=None, player=self.ui))
                result = r or "Done."

            elif name == "screen_process":
                threading.Thread(
                    target=screen_process,
                    kwargs={"parameters": args, "response": None,
                            "player": self.ui, "session_memory": None},
                    daemon=True
                ).start()
                result = "Vision module activated. Stay completely silent — vision module will speak directly."

            elif name == "computer_settings":
                r = await loop.run_in_executor(None, lambda: computer_settings(parameters=args, response=None, player=self.ui))
                result = r or "Done."

            elif name == "desktop_control":
                r = await loop.run_in_executor(None, lambda: desktop_control(parameters=args, player=self.ui))
                result = r or "Done."

            elif name == "code_helper":
                r = await loop.run_in_executor(None, lambda: code_helper(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."

            elif name == "dev_agent":
                r = await loop.run_in_executor(None, lambda: dev_agent(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."
                record("system", "JARVIS code change", str(result), source="dev_agent", status="completed")

            elif name == "programming_workflow":
                r = await loop.run_in_executor(
                    None,
                    lambda: programming_workflow(parameters=args, player=self.ui, speak=self.speak),
                )
                result = r or "Programming workflow finished."
                record("system", "Programming workflow", str(result), source="programming_workflow", status="completed")

            elif name == "agent_task":
                from agent.task_queue import get_queue, TaskPriority
                priority_map = {"low": TaskPriority.LOW, "normal": TaskPriority.NORMAL, "high": TaskPriority.HIGH}
                priority = priority_map.get(args.get("priority", "normal").lower(), TaskPriority.NORMAL)
                task_id  = get_queue().submit(
                    goal=args.get("goal", ""),
                    priority=priority,
                    speak=self.speak,
                    context=args.get("context", ""),
                    max_steps=args.get("max_steps", 12),
                )
                record(
                    "tasks", f"Agent task {task_id}", args.get("goal", ""),
                    source="agent_task", status="open",
                )
                result   = f"Task started (ID: {task_id})."

            elif name == "swarm_task":
                if _SWARM_AVAILABLE:
                    swarm     = get_swarm()
                    query     = args.get("query", "")
                    max_ag    = min(int(args.get("max_agents", 5)), 60)
                    context   = args.get("context", "")
                    r = await loop.run_in_executor(
                        None,
                        lambda: swarm.run(
                            query=query,
                            max_agents=max_ag,
                            speak=self.speak,
                            context=context,
                        )
                    )
                    result = r or "Swarm hat keine Antwort geliefert."
                else:
                    result = "Multi-Agent-System nicht verfügbar (openai-Paket installieren: pip install openai)."

            elif name == "composio_action":
                if _SWARM_AVAILABLE:
                    bridge = get_bridge()
                    task   = args.get("task", "")
                    if not bridge.is_configured:
                        result = "Composio nicht konfiguriert. Bitte composio_api_key in config/api_keys.json eintragen und 'pip install composio-openai' ausführen."
                    else:
                        r = await loop.run_in_executor(
                            None,
                            lambda: bridge.run_natural_language(
                                task=task,
                                speak=self.speak,
                            )
                        )
                        result = r or "Composio-Aktion abgeschlossen."
                else:
                    result = "Composio-Modul nicht verfügbar."

            elif name == "web_search":
                r = await loop.run_in_executor(None, lambda: web_search_action(parameters=args, player=self.ui))
                result = r or "Done."
            elif name == "file_processor":
                if not args.get("file_path") and self.ui.current_file:
                    args["file_path"] = self.ui.current_file
                r = await loop.run_in_executor(
                    None,
                    lambda: file_processor(parameters=args, player=self.ui, speak=self.speak)
                )
                result = r or "Done."

            elif name == "computer_control":
                r = await loop.run_in_executor(None, lambda: computer_control(parameters=args, player=self.ui))
                result = r or "Done."

            elif name == "game_updater":
                r = await loop.run_in_executor(None, lambda: game_updater(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."

            elif name == "flight_finder":
                r = await loop.run_in_executor(None, lambda: flight_finder(parameters=args, player=self.ui))
                result = r or "Done."

            elif name == "system_info":
                r = await loop.run_in_executor(None, lambda: system_info(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."

            elif name == "process_manager":
                r = await loop.run_in_executor(None, lambda: process_manager(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."

            elif name == "network_manager":
                r = await loop.run_in_executor(None, lambda: network_manager(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."

            elif name == "power_manager":
                r = await loop.run_in_executor(None, lambda: power_manager(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."

            elif name == "credential_manager":
                r = await loop.run_in_executor(None, lambda: credential_manager(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."

            elif name == "download_assistant":
                r = await loop.run_in_executor(None, lambda: download_assistant(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."

            elif name == "amazon_shopper":
                r = await loop.run_in_executor(None, lambda: amazon_shopper(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."

            elif name == "obsidian_brain":
                r = await loop.run_in_executor(None, lambda: obsidian_brain(parameters=args, player=self.ui))
                result = r or "Done."

            elif name == "gesture_diagnostics":
                r = await loop.run_in_executor(None, lambda: gesture_diagnostics(parameters=args, player=self.ui))
                result = r or "Done."

            elif name == "auto_trader":
                r = await loop.run_in_executor(None, lambda: auto_trader_tool(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."

            elif name == "get_datetime":
                result = get_datetime_tool(args)

            elif name == "read_own_code":
                r = await loop.run_in_executor(None, lambda: read_own_code(parameters=args, player=self.ui))
                result = r or "Done."

            elif name == "ui_mode":
                mode = (args.get("action") or "toggle").lower()
                try:
                    self.ui.set_ui_mode(mode)
                    result = ("Minimalansicht aktiv — nur ich." if mode == "minimal"
                              else "Dashboard eingeblendet, Boss." if mode == "dashboard"
                              else "Ansicht umgeschaltet.")
                except Exception as e:
                    result = f"UI-Umschaltung fehlgeschlagen: {e}"

            elif name == "hologram_control":
                action = (args.get("action") or "show").lower().strip()
                subject = (args.get("subject") or "").strip()
                detailed_terms = ("im detail", "zerleg", "explosionsansicht", "exploded", "bauteil")
                if action == "show" and (
                    is_arc_reactor_detail_request(subject)
                    or any(term in subject.lower() for term in detailed_terms)
                ):
                    action = "detail"
                try:
                    self.ui.control_model(action, subject)
                    if action == "focus":
                        result = (
                            f"3-D focus active for '{subject or 'the current model'}'. "
                            "Now explain the focused topic concisely to the user."
                        )
                    elif action == "detail":
                        result = (
                            f"Detailed 3-D breakdown started for '{subject or 'the current model'}'. "
                            "Explain the visible components and the animation concisely to the user."
                        )
                    elif action == "hide":
                        result = "3-D display closed."
                    else:
                        result = (
                            f"3-D model displayed for '{subject or 'hologram'}'. "
                            "JARVIS is in the corner; the user can now say 'fokussiere ...'."
                        )
                except Exception as e:
                    result = f"3-D display failed: {e}"

            elif name == "world_news_globe":
                self._trigger_world_news_globe()
                result = (
                    "World Intel globe opened. Ask the user to click a country; "
                    "the current headlines will be loaded and spoken automatically."
                )

            elif name == "shutdown_jarvis":
                self.ui.write_log("SYS: Shutdown requested.")
                self.speak("Goodbye, sir.")
                def _shutdown():
                    import time, os
                    time.sleep(1)
                    os._exit(0)
                threading.Thread(target=_shutdown, daemon=True).start()

            else:
                result = f"Unknown tool: {name}"

        except Exception as e:
            result = f"Tool '{name}' failed: {e}"
            traceback.print_exc()
            self.speak_error(name, e)

        if not self.ui.muted:
            self.ui.set_state("LISTENING")

        print(f"[JARVIS] 📤 {name} → {str(result)[:80]}")
        return types.FunctionResponse(
            id=fc.id, name=name,
            response={"result": result}
        )

    async def _send_realtime(self):
        while True:
            msg = await self.out_queue.get()
            await self.session.send_realtime_input(media=msg)

    async def _listen_audio(self):
        print("[JARVIS] 🎤 Mic started")
        loop = asyncio.get_event_loop()
        settings = load_barge_in_settings()
        gate = BargeInGate(
            threshold=float(settings["barge_in_rms_threshold"]),
            consecutive_blocks=int(settings["barge_in_consecutive_blocks"]),
            hangover_blocks=int(settings["barge_in_hangover_blocks"]),
        )
        barge_in_enabled = bool(settings["barge_in_enabled"])

        def callback(indata, frames, time_info, status):
            with self._speaking_lock:
                jarvis_speaking = self._is_speaking
            data = indata.tobytes()
            should_forward = (
                not jarvis_speaking
                or (barge_in_enabled and gate.should_forward(data, jarvis_speaking=True))
            )
            if should_forward and not self.ui.muted:
                # Safely put to queue only if it's not full to prevent asyncio.QueueFull flood
                def safe_put():
                    if not self.out_queue.full():
                        self.out_queue.put_nowait({"data": data, "mime_type": "audio/pcm"})
                loop.call_soon_threadsafe(safe_put)

        try:
            with sd.InputStream(
                samplerate=SEND_SAMPLE_RATE,
                channels=CHANNELS,
                dtype="int16",
                blocksize=CHUNK_SIZE,
                callback=callback,
            ):
                print("[JARVIS] 🎤 Mic stream open")
                while True:
                    await asyncio.sleep(0.1)
        except Exception as e:
            print(f"[JARVIS] ❌ Mic: {e}")
            raise

    async def _receive_audio(self):
        print("[JARVIS] 👂 Recv started")
        out_buf, in_buf = [], []

        try:
            while True:
                async for response in self.session.receive():

                    if response.data:
                        if self._turn_done_event and self._turn_done_event.is_set():
                            self._turn_done_event.clear()
                        self.audio_in_queue.put_nowait(response.data)

                    if response.server_content:
                        sc = response.server_content

                        if sc.interrupted:
                            while self.audio_in_queue and not self.audio_in_queue.empty():
                                try:
                                    self.audio_in_queue.get_nowait()
                                except asyncio.QueueEmpty:
                                    break
                            if self._playback_interrupt_event:
                                self._playback_interrupt_event.set()
                            self.set_speaking(False)
                            out_buf = []
                            self.ui.write_log("SYS: JARVIS interrupted by user voice.")

                        if sc.output_transcription and sc.output_transcription.text:
                            txt = _clean_transcript(sc.output_transcription.text)
                            if txt:
                                out_buf.append(txt)

                        if sc.input_transcription and sc.input_transcription.text:
                            txt = _clean_transcript(sc.input_transcription.text)
                            if txt:
                                in_buf.append(txt)

                        if sc.turn_complete:
                            if self._turn_done_event:
                                self._turn_done_event.set()

                            full_in = " ".join(in_buf).strip()
                            if full_in:
                                self.ui.write_log(f"You: {full_in}")
                                if is_daddys_home_phrase(full_in):
                                    self._trigger_daddys_home_mode()
                                else:
                                    youtube_params = parse_youtube_command(full_in)
                                    if youtube_params:
                                        self._trigger_youtube_action(youtube_params)
                            in_buf = []

                            full_out = " ".join(out_buf).strip()
                            if full_out:
                                self.ui.write_log(f"Jarvis: {full_out}")
                            out_buf = []

                    if response.tool_call:
                        fn_responses = []
                        for fc in response.tool_call.function_calls:
                            print(f"[JARVIS] 📞 {fc.name}")
                            fr = await self._execute_tool(fc)
                            fn_responses.append(fr)
                        await self.session.send_tool_response(
                            function_responses=fn_responses
                        )
        except Exception as e:
            print(f"[JARVIS] ❌ Recv: {e}")
            traceback.print_exc()
            raise

    async def _play_audio(self):
        print("[JARVIS] 🔊 Play started")

        stream = sd.RawOutputStream(
            samplerate=RECEIVE_SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            blocksize=CHUNK_SIZE,
        )
        stream.start()

        try:
            while True:
                if self._playback_interrupt_event and self._playback_interrupt_event.is_set():
                    stream.abort()
                    stream.start()
                    self._playback_interrupt_event.clear()
                    self.set_speaking(False)
                try:
                    chunk = await asyncio.wait_for(
                        self.audio_in_queue.get(),
                        timeout=0.1
                    )
                except asyncio.TimeoutError:
                    if (
                        self._turn_done_event
                        and self._turn_done_event.is_set()
                        and self.audio_in_queue.empty()
                    ):
                        self.set_speaking(False)
                        self._turn_done_event.clear()
                    continue
                self.set_speaking(True)
                await asyncio.to_thread(stream.write, chunk)
        except Exception as e:
            print(f"[JARVIS] ❌ Play: {e}")
            raise
        finally:
            self.set_speaking(False)
            stream.stop()
            stream.close()

    async def run(self):
        client = genai.Client(
            api_key=_get_api_key(),
            http_options={"api_version": "v1beta"}
        )

        # Load native Composio tools
        load_native_composio_tools(client)

        try:
            start_self_diagnosis_watcher()
            print("[JARVIS] Obsidian self-diagnosis watcher active")
        except Exception as e:
            record_error("self_diagnosis", "startup", e)

        # Auto-Trading-Wächter starten (Idle-Detection + Nacht-Schicht)
        try:
            start_trading_watcher(speak=self.speak, ui=self.ui)
            print("[JARVIS] 📈 Trading-Wächter aktiv (20min Idle → TradingView)")
        except Exception as e:
            print(f"[JARVIS] ⚠️ Trading-Wächter nicht gestartet: {e}")

        while True:
            try:
                print("[JARVIS] 🔌 Connecting...")
                self.ui.set_state("THINKING")
                config = self._build_config()

                async with (
                    client.aio.live.connect(model=LIVE_MODEL, config=config) as session,
                    asyncio.TaskGroup() as tg,
                ):
                    self.session        = session
                    self._loop          = asyncio.get_event_loop()
                    self.audio_in_queue = asyncio.Queue()
                    self.out_queue      = asyncio.Queue(maxsize=10)
                    self._turn_done_event = asyncio.Event()
                    self._playback_interrupt_event = asyncio.Event()

                    print("[JARVIS] ✅ Connected.")
                    self.ui.set_state("LISTENING")
                    self.ui.write_log("SYS: JARVIS online.")

                    # Zeitbewusste Begrüßung ("Nacht zum Tag machen, Boss?")
                    if not self._greeted:
                        self._greeted = True
                        try:
                            self.speak(get_greeting_instruction())
                        except Exception as e:
                            print(f"[JARVIS] ⚠️ Begrüßung fehlgeschlagen: {e}")

                    tg.create_task(self._send_realtime())
                    tg.create_task(self._listen_audio())
                    tg.create_task(self._receive_audio())
                    tg.create_task(self._play_audio())

            except Exception as e:
                print(f"[JARVIS] ⚠️ {e}")
                traceback.print_exc()
            self.set_speaking(False)
            self.ui.set_state("THINKING")
            print("[JARVIS] 🔄 Reconnecting in 3s...")
            await asyncio.sleep(3)

def main():
    ui = JarvisUI("face.png")

    def runner():
        ui.wait_for_api_key()
        jarvis = JarvisLive(ui)
        try:
            asyncio.run(jarvis.run())
        except KeyboardInterrupt:
            print("\n🔴 Shutting down...")

    threading.Thread(target=runner, daemon=True).start()
    ui.root.mainloop()

if __name__ == "__main__":
    main()
