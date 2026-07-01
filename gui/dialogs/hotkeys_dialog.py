from PySide6.QtCore import Qt, QSettings
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

_QT_SPECIAL_KEYS = {
    Qt.Key.Key_F1: "f1",   Qt.Key.Key_F2: "f2",   Qt.Key.Key_F3: "f3",
    Qt.Key.Key_F4: "f4",   Qt.Key.Key_F5: "f5",   Qt.Key.Key_F6: "f6",
    Qt.Key.Key_F7: "f7",   Qt.Key.Key_F8: "f8",   Qt.Key.Key_F9: "f9",
    Qt.Key.Key_F10: "f10", Qt.Key.Key_F11: "f11", Qt.Key.Key_F12: "f12",
    Qt.Key.Key_Return:   "enter",     Qt.Key.Key_Enter:    "enter",
    Qt.Key.Key_Space:    "space",     Qt.Key.Key_Backspace: "backspace",
    Qt.Key.Key_Delete:   "delete",   Qt.Key.Key_Insert:   "insert",
    Qt.Key.Key_Home:     "home",     Qt.Key.Key_End:      "end",
    Qt.Key.Key_PageUp:   "page_up",  Qt.Key.Key_PageDown: "page_down",
    Qt.Key.Key_Up:       "up",       Qt.Key.Key_Down:     "down",
    Qt.Key.Key_Left:     "left",     Qt.Key.Key_Right:    "right",
    Qt.Key.Key_Tab:      "tab",      Qt.Key.Key_Escape:   "esc",
}

_MODIFIER_KEYS = frozenset({
    Qt.Key.Key_Control, Qt.Key.Key_Shift,
    Qt.Key.Key_Alt, Qt.Key.Key_Meta, Qt.Key.Key_AltGr,
})

_DISPLAY_MAP = {
    "ctrl": "Ctrl", "alt": "Alt", "shift": "Shift",
    "enter": "Enter", "space": "Space", "backspace": "Backspace",
    "delete": "Delete", "insert": "Insert",
    "home": "Home", "end": "End",
    "page_up": "Page Up", "page_down": "Page Down",
    "up": "Up", "down": "Down", "left": "Left", "right": "Right",
    "tab": "Tab", "esc": "Esc",
}


def pynput_to_display(pynput_str: str) -> str:
    """Convert a pynput GlobalHotKeys string to a human-readable label.
    e.g. '<ctrl>+<f9>' → 'Ctrl + F9'
    """
    parts = []
    for segment in pynput_str.split("+"):
        if segment.startswith("<") and segment.endswith(">"):
            name = segment[1:-1]
            if name.startswith("f") and name[1:].isdigit():
                parts.append(name.upper())
            else:
                parts.append(_DISPLAY_MAP.get(name, name.capitalize()))
        else:
            parts.append(segment.upper())
    return " + ".join(parts)


def _qt_key_to_pynput(event) -> str | None:
    """Convert a Qt key-press event to a pynput GlobalHotKeys string.
    Returns None for unsupported or standalone-modifier presses.
    """
    key = event.key()
    if key in _MODIFIER_KEYS:
        return None

    parts = []
    mods = event.modifiers()
    if mods & Qt.KeyboardModifier.ControlModifier:
        parts.append("<ctrl>")
    if mods & Qt.KeyboardModifier.AltModifier:
        parts.append("<alt>")
    if mods & Qt.KeyboardModifier.ShiftModifier:
        parts.append("<shift>")

    special = _QT_SPECIAL_KEYS.get(key)
    if special:
        parts.append(f"<{special}>")
    elif Qt.Key.Key_A <= key <= Qt.Key.Key_Z:
        parts.append(chr(key).lower())
    elif Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
        parts.append(chr(key))
    else:
        return None

    return "+".join(parts) if parts else None


class HotkeysDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Hotkeys")
        self.setMinimumWidth(320)

        self._settings = QSettings("tinytask", "tinytask")
        self._record_key = self._settings.value("hotkeys/record", "<f9>")
        self._play_key = self._settings.value("hotkeys/playback", "<f10>")
        self._capturing = None  # "record" | "play" | None

        layout = QVBoxLayout(self)

        group = QGroupBox("Global hotkeys")
        group_layout = QVBoxLayout(group)

        record_row = QHBoxLayout()
        record_row.addWidget(QLabel("Record / Stop recording:"))
        self._record_btn = QPushButton(pynput_to_display(self._record_key))
        self._record_btn.setCheckable(True)
        self._record_btn.clicked.connect(self._start_capture_record)
        record_row.addWidget(self._record_btn)
        group_layout.addLayout(record_row)

        play_row = QHBoxLayout()
        play_row.addWidget(QLabel("Play / Stop playback:"))
        self._play_btn = QPushButton(pynput_to_display(self._play_key))
        self._play_btn.setCheckable(True)
        self._play_btn.clicked.connect(self._start_capture_play)
        play_row.addWidget(self._play_btn)
        group_layout.addLayout(play_row)

        layout.addWidget(group)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _start_capture_record(self):
        self._capturing = "record"
        self._record_btn.setText("Press a key...")
        self._play_btn.setChecked(False)

    def _start_capture_play(self):
        self._capturing = "play"
        self._play_btn.setText("Press a key...")
        self._record_btn.setChecked(False)

    def keyPressEvent(self, event):
        if self._capturing is None:
            super().keyPressEvent(event)
            return
        pynput_str = _qt_key_to_pynput(event)
        if pynput_str:
            if self._capturing == "record":
                self._record_key = pynput_str
                self._record_btn.setText(pynput_to_display(pynput_str))
                self._record_btn.setChecked(False)
            else:
                self._play_key = pynput_str
                self._play_btn.setText(pynput_to_display(pynput_str))
                self._play_btn.setChecked(False)
            self._capturing = None
        event.accept()

    def _save_and_accept(self):
        self._settings.setValue("hotkeys/record", self._record_key)
        self._settings.setValue("hotkeys/playback", self._play_key)
        self.accept()
