"""Main dictation window"""

from __future__ import annotations

import logging

from PySide6.QtCore import QEvent, QObject, QSettings, Qt, QTimer, Signal
from PySide6.QtGui import QCloseEvent, QShortcut, QKeySequence, QWindowStateChangeEvent
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import config

logger = logging.getLogger(__name__)

APP_VERSION = "0.063"

RECOGNITION_LANGS = [
    ("Russian", "ru-RU"),
    ("English (US)", "en-US"),
    ("English (UK)", "en-GB"),
    ("Spanish", "es-ES"),
    ("French", "fr-FR"),
    ("German", "de-DE"),
    ("Italian", "it-IT"),
    ("Portuguese (Brazil)", "pt-BR"),
    ("Japanese", "ja-JP"),
    ("Chinese (Simplified)", "zh-CN"),
]

TRANSLATE_LANGS = [
    ("English", "English"),
    ("Spanish", "Spanish"),
    ("French", "French"),
    ("German", "German"),
    ("Russian", "Russian"),
    ("Italian", "Italian"),
    ("Portuguese", "Portuguese"),
    ("Japanese", "Japanese"),
    ("Chinese (Simplified)", "Simplified Chinese"),
]


class DictationWindow(QMainWindow):
    talk_state_changed = Signal(bool)

    btn_talk_toggled = Signal(bool)
    speech_lang_activated = Signal(str)
    punctuation_toggled = Signal(bool)
    window_hidden = Signal()
    minimize_requested = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Mic2Clip v{APP_VERSION}")
        self.resize(520, 420)

        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        self._settings = QSettings("Mic2Clip", "Mic2Clip")

        self._status_overlay = ""

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        status_row = QHBoxLayout()

        self.btn_talk = QPushButton("Talk")
        self.btn_talk.setCheckable(True)
        self.btn_talk.setStyleSheet("QPushButton:checked { background-color: #ff4c4c; color: white; }")
        self.btn_talk.toggled.connect(self.btn_talk_toggled.emit)
        status_row.addWidget(self.btn_talk)

        self._status = QLineEdit("")
        self._status.setReadOnly(True)
        self._status.setFrame(False)
        self._status.setStyleSheet("background: transparent;")
        status_row.addWidget(self._status, stretch=1)


        status_row.addWidget(QLabel("Recognition:"))
        self.combo_speech = QComboBox()
        for label, _ in RECOGNITION_LANGS:
            self.combo_speech.addItem(label)
        self.combo_speech.activated.connect(self._on_speech_lang_activated)
        status_row.addWidget(self.combo_speech)
        layout.addLayout(status_row)

        editor_layout = QHBoxLayout()
        self.btn_clear = QPushButton("X")
        self.btn_clear.setFixedSize(24, 24)
        self.btn_clear.clicked.connect(self._on_clear_editor)
        editor_layout.addWidget(self.btn_clear, alignment=Qt.AlignmentFlag.AlignTop)

        self.editor = QTextEdit()
        self.editor.setPlaceholderText("Recognized and edited text appears here…")
        self.editor.setStyleSheet("background-color: #f0f0f0;")
        editor_layout.addWidget(self.editor, stretch=1)
        layout.addLayout(editor_layout, stretch=1)

        row = QHBoxLayout()
        self.btn_copy = QPushButton("Copy to clipboard")
        self.btn_copy.clicked.connect(self._copy_clipboard)
        row.addWidget(self.btn_copy)

        QShortcut(QKeySequence(Qt.KeyboardModifier.ControlModifier | Qt.Key.Key_Return), self).activated.connect(self._copy_clipboard)
        QShortcut(QKeySequence(Qt.KeyboardModifier.ControlModifier | Qt.Key.Key_Enter), self).activated.connect(self._copy_clipboard)

        self.btn_polish = QPushButton("Improve text (Gemini)")
        self.btn_polish.clicked.connect(self._on_polish)
        row.addWidget(self.btn_polish)

        QShortcut(QKeySequence(Qt.KeyboardModifier.ControlModifier | Qt.Key.Key_Space), self).activated.connect(self._on_polish)

        self.btn_translate = QPushButton("Translate")
        self.btn_translate.clicked.connect(self._on_translate)
        row.addWidget(self.btn_translate)

        self.combo_lang = QComboBox()
        for label, _ in TRANSLATE_LANGS:
            self.combo_lang.addItem(label)
        row.addWidget(self.combo_lang)
        layout.addLayout(row)

        chk_row = QHBoxLayout()
        self.chk_close_after_copy = QCheckBox("Close window after copy")
        self.chk_close_after_copy.setChecked(False)
        chk_row.addWidget(self.chk_close_after_copy)

        self.chk_delete_after_copy = QCheckBox("Delete after copy")
        self.chk_delete_after_copy.setChecked(False)
        chk_row.addWidget(self.chk_delete_after_copy)

        self.chk_punctuation = QCheckBox("Auto punctuation")
        self.chk_punctuation.setChecked(
            self._settings.value("auto_punctuation", True, type=bool)
        )
        self.chk_punctuation.toggled.connect(self._on_punctuation_toggled)
        chk_row.addWidget(self.chk_punctuation)
        chk_row.addStretch()
        layout.addLayout(chk_row)

        self._hint = QLabel("")
        self._hint.setWordWrap(True)
        layout.addWidget(self._hint)

        self._restore_settings()
        self.combo_lang.currentIndexChanged.connect(self._persist_ui_settings)
        self.chk_close_after_copy.stateChanged.connect(self._persist_ui_settings)
        self.chk_delete_after_copy.stateChanged.connect(self._persist_ui_settings)

    def _on_speech_lang_activated(self, index: int) -> None:
        if index < 0:
            return
        code = RECOGNITION_LANGS[index][1]
        self._settings.setValue("speechLangCode", code)
        self.speech_lang_activated.emit(code)

    def _restore_settings(self):
        geom = self._settings.value("geometry")
        if geom is not None:
            self.restoreGeometry(geom)
        saved_speech = self._settings.value("speechLangCode", "ru-RU", type=str)
        self.combo_speech.blockSignals(True)
        for i, (_, code) in enumerate(RECOGNITION_LANGS):
            if code == saved_speech:
                self.combo_speech.setCurrentIndex(i)
                break
        self.combo_speech.blockSignals(False)
        n = self.combo_lang.count()
        if n > 0:
            idx = int(self._settings.value("translateLangIndex", 0, type=int))
            last_index = 0
            for i in range(n):
                last_index = i
            self.combo_lang.setCurrentIndex(min(max(0, idx), last_index))
        self.chk_close_after_copy.setChecked(
            self._settings.value("closeAfterCopy", False, type=bool)
        )
        self.chk_delete_after_copy.setChecked(
            self._settings.value("deleteAfterCopy", False, type=bool)
        )

    def _persist_ui_settings(self, *_args: object):
        self._settings.setValue("translateLangIndex", self.combo_lang.currentIndex())
        self._settings.setValue("closeAfterCopy", self.chk_close_after_copy.isChecked())
        self._settings.setValue("deleteAfterCopy", self.chk_delete_after_copy.isChecked())

    def _is_minimized(self) -> bool:
        return bool(self.windowState() & Qt.WindowState.WindowMinimized)

    def _on_punctuation_toggled(self, checked: bool) -> None:
        self._settings.setValue("auto_punctuation", checked)
        self.punctuation_toggled.emit(checked)

    def _refresh_status_label(self) -> None:
        self._status.setText(self._status_overlay)
        self._status.setCursorPosition(len(self._status_overlay))

    def _set_status_overlay(self, text: str) -> None:
        self._status_overlay = text
        self._refresh_status_label()

    def _clear_status_overlay(self) -> None:
        self._status_overlay = ""
        self._refresh_status_label()

    def set_status_overlay(self, text: str):
        self._set_status_overlay(text)

    def event(self, event: QEvent) -> bool:  # noqa: N802
        if event.type() == QEvent.Type.WindowActivate:
            self.editor.setStyleSheet("background-color: #ffffff;")
            if not self.btn_talk.isChecked():
                self.btn_talk.setChecked(True)
        elif event.type() == QEvent.Type.WindowDeactivate:
            self.editor.setStyleSheet("background-color: #f0f0f0;")
        elif event.type() == QEvent.Type.Expose:
            if self.windowHandle() and not self.windowHandle().isExposed():
                self.hide()
        return super().event(event)

    def changeEvent(self, event: QEvent):  # noqa: N802
        if event.type() == QEvent.Type.WindowStateChange:
            if self.windowState() & Qt.WindowState.WindowMinimized:
                # User clicked the standard minimize button "-"
                # Switch to mini window instead of hiding to tray
                self.minimize_requested.emit()
                self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized)
        super().changeEvent(event)

    def hideEvent(self, event: QEvent):  # noqa: N802
        self._settings.setValue("geometry", self.saveGeometry())
        super().hideEvent(event)
        self.window_hidden.emit()

    def closeEvent(self, event: QCloseEvent):  # noqa: N802
        event.ignore()
        self.hide()

    def _on_clear_editor(self):
        self.editor.clear()
        self.editor.setFocus(Qt.FocusReason.PopupFocusReason)

    def _copy_clipboard(self):
        import pyperclip

        text = self.editor.toPlainText().strip()
        if not text:
            return
        try:
            pyperclip.copy(text)
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "Clipboard", str(e))
            return
        self._set_status_overlay("Copied to clipboard.")
        QTimer.singleShot(2000, self._clear_status_overlay)

        if self.chk_delete_after_copy.isChecked():
            self.editor.clear()
        if self.chk_close_after_copy.isChecked():
            self.hide()

    def _on_polish(self):
        import gemini_service
        from PySide6.QtGui import QTextCursor

        text = self.editor.toPlainText()
        if not text.strip():
            return

        was_listening = self.btn_talk.isChecked()
        if was_listening:
            self.btn_talk.setChecked(False)

        self._set_status_overlay("Improving...")
        QApplication.processEvents()
        try:
            improved = gemini_service.polish_text(text)
            self.editor.setPlainText(improved)
            cursor = self.editor.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.editor.setTextCursor(cursor)
            self.editor.ensureCursorVisible()
        except Exception as e:  # noqa: BLE001
            logger.exception("polish failed")
            QMessageBox.warning(self, "Gemini", str(e))
        finally:
            self._clear_status_overlay()
            self.editor.setFocus(Qt.FocusReason.PopupFocusReason)
            if was_listening:
                self.btn_talk.setChecked(True)

    def _on_translate(self):
        import gemini_service
        from PySide6.QtGui import QTextCursor

        text = self.editor.toPlainText()
        if not text.strip():
            return
        idx = self.combo_lang.currentIndex()
        if idx < 0:
            return
        target = TRANSLATE_LANGS[idx][1]

        # Stop listening during translation
        self.btn_talk.setChecked(False)
        self._set_status_overlay("Translating...")
        QApplication.processEvents()

        try:
            out = gemini_service.translate_text(text, target)
            self.editor.setPlainText(out)
            cursor = self.editor.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.editor.setTextCursor(cursor)
            self.editor.ensureCursorVisible()
        except Exception as e:  # noqa: BLE001
            logger.exception("translate failed")
            QMessageBox.warning(self, "Gemini", str(e))
        finally:
            self._clear_status_overlay()
            self.editor.setFocus(Qt.FocusReason.PopupFocusReason)
            # Always enable listening after translation
            self.btn_talk.setChecked(True)
