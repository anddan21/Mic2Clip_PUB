"""Qt signals for speech worker → GUI thread."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class SpeechSignals(QObject):
    partial = Signal(str)
    final = Signal(str)
    error = Signal(str)
    closed = Signal()
