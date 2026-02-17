"""Shared utilities for Guitar Pro YouTube Sync."""

import json
import sys
from pathlib import Path


def resource_path(relative_path: str) -> Path:
    """Resolve bundled resource path (works in dev + PyInstaller)."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / relative_path
    return Path(__file__).parent / relative_path


def get_ffmpeg_dir() -> str:
    """Return directory containing bundled ffmpeg, or empty string for system PATH."""
    d = resource_path("ffmpeg_bin")
    return str(d) if d.exists() else ""


CONFIG_DIR = Path.home() / ".songstrr-sync"
CONFIG_FILE = CONFIG_DIR / "config.json"


def load_config() -> dict:
    """Load saved preferences (e.g. last used cookie browser)."""
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_config(config: dict) -> None:
    """Persist preferences to disk."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2))
