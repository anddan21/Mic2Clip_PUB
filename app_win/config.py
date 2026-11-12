"""Configuration: settings.cfg for app options, .env for API secrets."""

from __future__ import annotations

import os
import re
from pathlib import Path

from dotenv import load_dotenv

_APP_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _APP_DIR.parent

_CFG_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _load_dotenv() -> None:
    """Load the first existing file: repo/.env, then app_win/.env."""
    for path in (_REPO_ROOT / ".env", _APP_DIR / ".env"):
        if path.is_file():
            load_dotenv(path, override=True)
            break


def _parse_settings_line(line: str) -> tuple[str, str] | None:
    line = line.strip()
    if not line or line.startswith("#") or line.startswith(";"):
        return None
    if line.startswith("[") and line.endswith("]"):
        return None
    if "=" not in line:
        return None
    key, _, value = line.partition("=")
    key = key.strip()
    value = value.strip()
    if not key or not _CFG_KEY.match(key):
        return None
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        value = value[1:-1]
    return key, value


def _load_settings_cfg() -> dict[str, str]:
    """Load app_win/settings.cfg."""
    path = _APP_DIR / "settings.cfg"
    settings: dict[str, str] = {}
    if not path.is_file():
        return settings
    with path.open(encoding="utf-8") as fh:
        for raw in fh:
            parsed = _parse_settings_line(raw)
            if parsed:
                settings[parsed[0]] = parsed[1]
    return settings


def _setting(name: str, default: str = "") -> str:
    """Value from settings.cfg, overridable by environment variable."""
    return os.environ.get(name, _SETTINGS.get(name, default))


def _setting_bool(name: str, default: bool = False) -> bool:
    raw = _setting(name, "true" if default else "false").strip().lower()
    return raw in ("1", "true", "yes", "on")


_load_dotenv()
_SETTINGS = _load_settings_cfg()

# Google Cloud Speech to Text: path to service account JSON (.env only)
GOOGLE_APPLICATION_CREDENTIALS = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")

# Gemini API key (.env only)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# settings.cfg (+ optional env override)
GEMINI_MODEL = _setting("GEMINI_MODEL", "gemini-2.0-flash")
DEFAULT_HOTKEY = _setting("MIC2CLIP_HOTKEY", "alt+q")

AUTO_HIDE_SECONDS = int(_setting("AUTO_HIDE", "30"))

SAMPLE_RATE = int(_setting("SAMPLE_RATE", "16000"))
CHANNELS = int(_setting("CHANNELS", "1"))

SETTINGS_CFG_PATH = _APP_DIR / "settings.cfg"
