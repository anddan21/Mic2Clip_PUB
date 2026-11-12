"""Mic2Clip — Windows tray dictation app entry point."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

# Suppress gRPC and absl warnings (e.g. ALTS creds ignored) before any Google imports
os.environ["GRPC_VERBOSITY"] = "NONE"
os.environ["GRPC_TRACE"] = ""
os.environ["GLOG_minloglevel"] = "3"

# Running `python main.py` from app_win keeps imports stable
_APP_DIR = Path(__file__).resolve().parent
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

from PySide6.QtCore import QCoreApplication, QObject, QSharedMemory, Qt, Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QMenu,
    QMessageBox,
    QStyle,
    QSystemTrayIcon,
)

import config
import hotkeys
from dictation_window import DictationWindow
from mini_window import MiniWindow
from app_controller import AppController


class _HotkeyBridge(QObject):
    """keyboard invokes callbacks from a hook thread; Qt GUI must run on the main thread."""

    toggle_requested = Signal()


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logger = logging.getLogger("main")
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("Mic2Clip")
    QCoreApplication.setOrganizationName("Mic2Clip")

    mem = QSharedMemory("Mic2ClipSingleInstance")
    if not mem.create(1):
        QMessageBox.warning(
            None,
            "Mic2Clip",
            "Another instance of Mic2Clip is already running.",
        )
        return 0

    dictation_window = DictationWindow()
    mini_window = MiniWindow()
    controller = AppController(dictation_window, mini_window)

    # Wire up signals
    dictation_window.btn_talk_toggled.connect(controller.set_talking_state)
    dictation_window.speech_lang_activated.connect(controller.set_language_code)
    dictation_window.punctuation_toggled.connect(controller.set_automatic_punctuation)
    dictation_window.window_hidden.connect(controller.check_visibility_and_stop)
    dictation_window.minimize_requested.connect(controller.show_mini_window)

    mini_window.btn_talk_toggled.connect(controller.set_talking_state)
    mini_window.btn_main_clicked.connect(controller.show_main_window)
    mini_window.window_hidden.connect(controller.check_visibility_and_stop)

    controller.talk_state_changed.connect(dictation_window.btn_talk.setChecked)
    controller.talk_state_changed.connect(mini_window.btn_talk.setChecked)
    controller.status_overlay_changed.connect(dictation_window.set_status_overlay)
    controller.status_overlay_changed.connect(mini_window.set_status_overlay)

    hotkey_bridge = _HotkeyBridge(app)
    hotkey_bridge.toggle_requested.connect(
        controller.toggle_visible,
        Qt.ConnectionType.QueuedConnection,
    )

    icon_mic_white = QIcon(str(_APP_DIR / "icons" / "mic_white.svg"))
    icon_mic_red = QIcon(str(_APP_DIR / "icons" / "mic_red.svg"))

    tray = QSystemTrayIcon(app)
    tray.setIcon(icon_mic_white)
    menu = QMenu()
    act_show = QAction("Show / hide dictation", app)
    act_show.triggered.connect(controller.toggle_visible)
    menu.addAction(act_show)
    act_quit = QAction("Quit", app)
    act_quit.triggered.connect(app.quit)
    menu.addAction(act_quit)
    tray.setContextMenu(menu)

    def on_talk_state_changed(is_talking: bool) -> None:
        if is_talking:
            tray.setIcon(icon_mic_red)
        else:
            tray.setIcon(icon_mic_white)

    controller.talk_state_changed.connect(on_talk_state_changed)

    tray.show()

    def tray_activated(reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            controller.toggle_visible()

    tray.activated.connect(tray_activated)

    err = hotkeys.register_toggle_hotkey(
        config.DEFAULT_HOTKEY,
        hotkey_bridge.toggle_requested.emit,
    )
    if err:
        dictation_window._hint.setText(  # noqa: SLF001
            f"Hotkey ({config.DEFAULT_HOTKEY}) not active: {err}. "
            "Use tray menu Show/hide or run as administrator if required."
        )
    else:
        dictation_window._hint.setText(  # noqa: SLF001
            f"Tray icon active. Hotkey: {config.DEFAULT_HOTKEY} (MIC2CLIP_HOTKEY in settings.cfg). "
            "Set GOOGLE_APPLICATION_CREDENTIALS and GEMINI_API_KEY in .env for cloud features."
        )

    logger.info("Mic2Clip ready (tray + hotkey); starting event loop.")
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
