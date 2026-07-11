from __future__ import annotations

import json
import platform
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
CONFIG_DIR = BASE_DIR / "config"
CONFIG_PATH = CONFIG_DIR / "api_keys.json"
EXAMPLE_PATH = CONFIG_DIR / "api_keys.example.json"


def _prompt(label: str, current: str = "", required: bool = False) -> str:
    suffix = " required" if required else " optional"
    if current:
        value = input(f"{label} [{suffix}, ENTER keeps current]: ").strip()
        return value or current
    return input(f"{label} [{suffix}]: ").strip()


def _default_config() -> dict:
    if EXAMPLE_PATH.exists():
        return json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))
    return {
        "gemini_api_key": "",
        "openrouter_api_key": "",
        "composio_api_key": "",
        "anthropic_api_key": "",
        "composio_native_apps": ["gmail", "googlecalendar", "googletasks", "spotify", "github"],
        "os_system": platform.system().lower(),
        "camera_index": 0,
        "gesture_camera_enabled": True,
    }


def main() -> int:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    config = _default_config()

    if CONFIG_PATH.exists():
        try:
            existing = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            config.update(existing)
        except Exception:
            print("Existing config/api_keys.json could not be parsed. Recreating it.")

    print("MARK XXXIX local API key setup")
    print("These values stay local. Do not commit config/api_keys.json.")
    print()

    config["gemini_api_key"] = _prompt("Gemini API key", config.get("gemini_api_key", ""), required=True)
    config["openrouter_api_key"] = _prompt("OpenRouter API key", config.get("openrouter_api_key", ""))
    config["composio_api_key"] = _prompt("Composio API key", config.get("composio_api_key", ""))
    config["anthropic_api_key"] = _prompt("Anthropic API key", config.get("anthropic_api_key", ""))

    detected = {"windows": "windows", "darwin": "mac", "linux": "linux"}.get(
        platform.system().lower(),
        "windows",
    )
    config["os_system"] = config.get("os_system") or detected

    CONFIG_PATH.write_text(json.dumps(config, indent=4), encoding="utf-8")
    print()
    print(f"Wrote local config: {CONFIG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
