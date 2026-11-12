"""Global hotkeys via the `keyboard` package (may require elevated rights on some setups)."""

from __future__ import annotations

import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)

def register_toggle_hotkey(combination: str, callback: Callable[[], None]) -> Optional[str]:
    """Register a global hotkey. Returns an error message string if registration failed."""
    try:
        import keyboard
    except ImportError:
        return "Package `keyboard` is not installed."
    try:
        keyboard.add_hotkey(combination, callback, suppress=False)
        return None
    except Exception as e:  # noqa: BLE001
        logger.exception("hotkey register failed")
        return str(e)
