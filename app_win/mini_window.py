"""Mini dictation window"""

from __future__ import annotations

import logging

from PySide6.QtCore import QEvent, QSettings, Qt, Signal
from PySide6.QtGui import QCloseEvent, QIcon, QMouseEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QVBoxLayout,
    QMainWindow,
    QPushButton,
    QWidget,
    QLineEdit,
)

logger = logging.getLogger(__name__)

from dictation_window import APP_VERSION

class MiniWindow(QMainWindow):
    btn_talk_toggled = Signal(bool)
    btn_main_clicked = Signal()
    window_hidden = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"v{APP_VERSION}")
        self.setWindowIcon(QIcon())

        flags = Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowCloseButtonHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        self.resize(220, 80)

        self._settings = QSettings("Mic2Clip", "Mic2Clip")

        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)

        # Top row: scrolling status text
        self._status_overlay = ""
        self._status = QLineEdit("")
        self._status.setReadOnly(True)
        self._status.setFrame(False)
        self._status.setStyleSheet("background: transparent; color: #555;")
        main_layout.addWidget(self._status)

        # Bottom row: buttons
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 0, 0, 0)

        from pathlib import Path
        _APP_DIR = Path(__file__).resolve().parent

        # [Square] [Mic] [Settings]
        self.btn_main = QPushButton("□")
        self.btn_main.setFixedSize(40, 40)
        self.btn_main.setStyleSheet("QPushButton { background: transparent; border: none; font-size: 24px; } QPushButton:hover { background: #e0e0e0; border-radius: 5px; }")
        self.btn_main.clicked.connect(self.btn_main_clicked.emit)
        btn_layout.addWidget(self.btn_main)

        icon_mic_red = QIcon(str(_APP_DIR / "icons" / "mic_red.svg"))
        self.btn_talk = QPushButton()
        self.btn_talk.setIcon(icon_mic_red)
        from PySide6.QtCore import QSize
        self.btn_talk.setIconSize(QSize(28, 28))
        self.btn_talk.setFixedSize(60, 40)
        self.btn_talk.setCheckable(True)
        self.btn_talk.setStyleSheet("""
            QPushButton { background: transparent; border: none; border-radius: 40px; }
            QPushButton:hover { background: #e0e0e0; }
            QPushButton:checked { background-color: #ffe5e5; }
        """)
        self.btn_talk.clicked.connect(self.hide)
        self.btn_talk.toggled.connect(self.btn_talk_toggled.emit)
        btn_layout.addWidget(self.btn_talk)

        icon_gear = QIcon(str(_APP_DIR / "icons" / "settings_gear.svg"))
        self.btn_settings = QPushButton()
        self.btn_settings.setIcon(icon_gear)
        self.btn_settings.setIconSize(QSize(24, 24))
        self.btn_settings.setFixedSize(40, 40)
        self.btn_settings.setStyleSheet("QPushButton { background: transparent; border: none; } QPushButton:hover { background: #e0e0e0; border-radius: 5px; }")
        # Settings is a dummy button for now
        btn_layout.addWidget(self.btn_settings)

        main_layout.addLayout(btn_layout)

        self._restore_settings()

    def set_status_overlay(self, text: str):
        self._status_overlay = text
        self._status.setText(self._status_overlay)
        self._status.setCursorPosition(len(self._status_overlay))

    def _restore_settings(self):
        geom = self._settings.value("mini_geometry")
        if geom is not None:
            self.restoreGeometry(geom)

    def _is_minimized(self) -> bool:
        return bool(self.windowState() & Qt.WindowState.WindowMinimized)

    def changeEvent(self, event: QEvent):  # noqa: N802
        if event.type() == QEvent.Type.WindowStateChange:
            if self.windowState() & Qt.WindowState.WindowMinimized:
                self.hide()
                self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized)
        super().changeEvent(event)

    def hideEvent(self, event: QEvent):  # noqa: N802
        self._settings.setValue("mini_geometry", self.saveGeometry())
        super().hideEvent(event)
        self.window_hidden.emit()

    def closeEvent(self, event: QCloseEvent):  # noqa: N802
        event.ignore()
        self.hide()
