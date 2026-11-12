"""Application Controller for Mic2Clip."""

import logging
import os
import re

from PySide6.QtCore import QObject, QSettings, Qt, QTimer, Signal
from PySide6.QtWidgets import QApplication

import config
import threading

from speech_service import StreamingDictationSession
from speech_signals import SpeechSignals

logger = logging.getLogger(__name__)


class AppController(QObject):
    talk_state_changed = Signal(bool)
    status_overlay_changed = Signal(str)

    def __init__(self, dictation_window, mini_window):
        super().__init__()
        self.dictation_window = dictation_window
        self.mini_window = mini_window

        self._settings = QSettings("Mic2Clip", "Mic2Clip")

        self._speech_bridge = SpeechSignals()
        self._session = StreamingDictationSession(
            on_partial=lambda t: self._speech_bridge.partial.emit(t),
            on_final=lambda t: self._speech_bridge.final.emit(t),
            on_error=lambda m: self._speech_bridge.error.emit(m),
            on_closed=lambda: self._speech_bridge.closed.emit(),
        )
        self._speech_bridge.partial.connect(self._on_partial_text)
        self._speech_bridge.final.connect(self._on_final_text)
        self._speech_bridge.error.connect(self._on_speech_error)
        self._speech_bridge.closed.connect(self._on_stream_closed)

        self._silence_timer = QTimer(self)
        self._silence_timer.setSingleShot(True)
        self._silence_timer.timeout.connect(self._on_silence_timeout)

        self.is_talking = False

        # Set automatic punctuation from settings
        auto_punct = self._settings.value("auto_punctuation", True, type=bool)
        self._session.set_automatic_punctuation(auto_punct)

        self.dictation_window.chk_punctuation.setChecked(auto_punct)

        self._apply_speech_language()

        # Warmup heavy dependencies in the background to prevent UI freezing
        threading.Thread(target=self._warmup_dependencies, daemon=True).start()

    def _warmup_dependencies(self):
        try:
            logger.info("Warming up dependencies in background...")
            import sounddevice as sd
            _ = sd.query_devices() # Force PortAudio initialization

            from google.cloud import speech_v1
            _ = speech_v1.SpeechClient
            logger.info("Dependencies warmed up.")
        except Exception as e:
            logger.warning(f"Background warmup encountered an issue: {e}")

    def _apply_speech_language(self) -> None:
        saved_speech = self._settings.value("speechLangCode", "ru-RU", type=str)
        self._session.set_language_code(saved_speech)

    def set_language_code(self, code: str):
        self._session.set_language_code(code)

    def set_automatic_punctuation(self, enabled: bool):
        self._session.set_automatic_punctuation(enabled)

    def _reset_silence_timer(self) -> None:
        if config.AUTO_HIDE_SECONDS > 0:
            self._silence_timer.start(config.AUTO_HIDE_SECONDS * 1000)

    def set_talking_state(self, talking: bool):
        if talking == self.is_talking:
            return

        self.is_talking = talking
        self.talk_state_changed.emit(talking)

        if talking:
            self.status_overlay_changed.emit("")
            self._session.start()
            self._reset_silence_timer()
        else:
            self._session.stop()
            self.status_overlay_changed.emit("")
            self._silence_timer.stop()

    def _on_stream_closed(self) -> None:
        if self.is_talking:
            # Automatically restart stream if the state is still talking
            QTimer.singleShot(50, self._session.start)
        else:
            self.set_talking_state(False)

    def toggle_visible(self):
        # If any window is visible and not minimized, hide them all
        if (self.dictation_window.isVisible() and not self.dictation_window._is_minimized()) or \
           (self.mini_window.isVisible() and not self.mini_window._is_minimized()):
            self.hide_all()
        else:
            self.show_mini_window()

    def hide_all(self):
        if self.dictation_window.isVisible():
            self.dictation_window.hide()
        if self.mini_window.isVisible():
            self.mini_window.hide()
        self.set_talking_state(False)

    def show_mini_window(self):
        if self.mini_window._is_minimized():
            self.mini_window.setWindowState(
                self.mini_window.windowState() & ~Qt.WindowState.WindowMinimized
            )
        self.mini_window.show()

        if self.dictation_window.isVisible():
            self.dictation_window.hide()

        if not self.is_talking:
            self.set_talking_state(True)

    def show_main_window(self):
        if self.dictation_window._is_minimized():
            self.dictation_window.setWindowState(
                self.dictation_window.windowState() & ~Qt.WindowState.WindowMinimized
            )
        self.dictation_window.show()

        if self.mini_window.isVisible():
            self.mini_window.hide()

        if not self.is_talking:
            self.set_talking_state(True)

    def check_visibility_and_stop(self):
        if not self.dictation_window.isVisible() and not self.mini_window.isVisible():
            self.set_talking_state(False)

    def _on_silence_timeout(self):
        self.hide_all()

    def _on_partial_text(self, text: str):
        self._reset_silence_timer()
        self.status_overlay_changed.emit(text)

    def _apply_dictation_commands(self, text: str) -> str:
        cfg_path = os.path.join(os.path.dirname(__file__), "commands.cfg")
        if not os.path.exists(cfg_path):
            return text

        commands = {}
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                for line in f:
                    clean_line = line.strip()
                    if not clean_line or clean_line.startswith("#") or clean_line.startswith("::"):
                        continue
                    if "=" in line:
                        word, symbol = line.split("=", 1)
                        word = word.strip()
                        symbol = symbol.rstrip("\n").replace("\\n", "\n")
                        if word:
                            commands[word] = symbol
        except Exception as e:  # noqa: BLE001
            logger.error("Failed to read commands.cfg: %s", e)
            return text

        sorted_words = sorted(commands.keys(), key=len, reverse=True)

        for word in sorted_words:
            symbol = commands[word]
            pattern = r'(?i)\s*\b' + re.escape(word) + r'\b'
            text = re.sub(pattern, lambda _: symbol, text)

        return text

    def _on_final_text(self, text: str):
        from PySide6.QtGui import QTextCursor

        self._reset_silence_timer()
        self.status_overlay_changed.emit("")
        text = self._apply_dictation_commands(text)

        if self.dictation_window.isActiveWindow() and self.dictation_window.editor.hasFocus():
            editor = self.dictation_window.editor
            cursor = editor.textCursor()
            if cursor.position() > 0:
                cursor.movePosition(QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.KeepAnchor, 1)
                prev_char = cursor.selectedText()
                cursor.clearSelection()
                if prev_char and prev_char not in (" ", "\n", "\t") and not text.startswith((",", ".", "!", "?", ":", ";", "\n")):
                    text = " " + text

            editor.insertPlainText(text)
            editor.ensureCursorVisible()

            full_text = editor.toPlainText()
            collapsed = re.sub(r' {2,}', ' ', full_text)
            if collapsed != full_text:
                editor.setPlainText(collapsed)
                cursor = editor.textCursor()
                cursor.movePosition(QTextCursor.MoveOperation.End)
                editor.setTextCursor(cursor)
                editor.ensureCursorVisible()
        else:
            try:
                import keyboard
                keyboard.write(text)
            except Exception as e:
                logger.error("Failed to write to external window: %s", e)

    def _on_speech_error(self, message: str):
        self.dictation_window._hint.setText(message)
        logger.warning("%s", message)
