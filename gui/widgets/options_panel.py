from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QFrame, QStackedWidget,
    QFormLayout, QSpinBox, QDoubleSpinBox, QLineEdit, QComboBox, QCheckBox,
    QPushButton, QApplication,
)
from PySide6.QtCore import Qt, Signal


# --- helpers ---

def _coord_spin() -> QSpinBox:
    s = QSpinBox()
    s.setRange(0, 7680)
    return s

def _dur_spin(min_val: float = 0.0, max_val: float = 3600.0) -> QDoubleSpinBox:
    s = QDoubleSpinBox()
    s.setRange(min_val, max_val)
    s.setDecimals(2)
    s.setSingleStep(0.1)
    return s

def _button_combo() -> QComboBox:
    c = QComboBox()
    c.addItems(["left", "right", "middle"])
    return c


# --- screen picker ---

class _ScreenPicker(QWidget):
    picked = Signal(int, int)
    cancelled = Signal()

    def __init__(self):
        _flags = (Qt.WindowType.FramelessWindowHint |
                  Qt.WindowType.WindowStaysOnTopHint)
        super().__init__(None, _flags)
        self.setWindowOpacity(0.01)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setGeometry(QApplication.primaryScreen().virtualGeometry())

        # Separate label so it isn't dimmed by the parent's near-zero opacity
        self._hint = QLabel("  Click to pick position  |  Esc to cancel  ")
        self._hint.setWindowFlags(_flags | Qt.WindowType.Tool)
        self._hint.setStyleSheet(
            "background:#1e1e1e; color:white; padding:8px 14px;"
            "border-radius:4px; font-size:13px;"
        )
        self._hint.adjustSize()
        sr = QApplication.primaryScreen().geometry()
        self._hint.move(sr.center().x() - self._hint.width() // 2, 20)
        self._hint.show()

        self.show()
        self.activateWindow()
        self.setFocus()

    def closeEvent(self, event):
        self._hint.close()
        super().closeEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.globalPosition().toPoint()
            screen = QApplication.screenAt(pos)
            ratio = screen.devicePixelRatio() if screen else 1.0
            self.picked.emit(round(pos.x() * ratio), round(pos.y() * ratio))
            self.close()
        elif event.button() == Qt.MouseButton.RightButton:
            self.cancelled.emit()
            self.close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()
            self.close()


# --- base ---

class _BaseOptions(QWidget):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._action = None
        self._loading = False

    def load(self, action):
        self._action = action
        self._loading = True
        self._populate(action)
        self._loading = False

    def _emit(self):
        if not self._loading and self._action is not None:
            self._apply(self._action)
            self.changed.emit()

    def _start_pick(self, on_picked):
        self._picker = _ScreenPicker()
        self._picker.picked.connect(lambda x, y: on_picked(x, y))

    def _populate(self, action): raise NotImplementedError(action)
    def _apply(self, action): raise NotImplementedError(action)


# --- per-action options widgets ---

class _ClickOptions(_BaseOptions):
    def __init__(self, parent=None):
        super().__init__(parent)
        form = QFormLayout(self)
        form.setContentsMargins(8, 8, 8, 8)
        self._x = _coord_spin()
        self._y = _coord_spin()
        self._btn = _button_combo()
        pick_btn = QPushButton("Pick position")
        pick_btn.clicked.connect(lambda: self._start_pick(
            lambda x, y: (self._x.setValue(x), self._y.setValue(y))
        ))
        form.addRow("X:", self._x)
        form.addRow("Y:", self._y)
        form.addRow("", pick_btn)
        form.addRow("Button:", self._btn)
        self._x.valueChanged.connect(self._emit)
        self._y.valueChanged.connect(self._emit)
        self._btn.currentTextChanged.connect(self._emit)

    def _populate(self, action):
        self._x.setValue(action.x)
        self._y.setValue(action.y)
        self._btn.setCurrentText(action.button)

    def _apply(self, action):
        action.x = self._x.value()
        action.y = self._y.value()
        action.button = self._btn.currentText()


class _RepeatClickOptions(_BaseOptions):
    def __init__(self, parent=None):
        super().__init__(parent)
        form = QFormLayout(self)
        form.setContentsMargins(8, 8, 8, 8)
        self._x = _coord_spin()
        self._y = _coord_spin()
        self._count = QSpinBox()
        self._count.setRange(1, 100000)
        self._interval = _dur_spin(0.01, 60.0)
        self._btn = _button_combo()
        pick_btn = QPushButton("Pick position")
        pick_btn.clicked.connect(lambda: self._start_pick(
            lambda x, y: (self._x.setValue(x), self._y.setValue(y))
        ))
        form.addRow("X:", self._x)
        form.addRow("Y:", self._y)
        form.addRow("", pick_btn)
        form.addRow("Count:", self._count)
        form.addRow("Interval (s):", self._interval)
        form.addRow("Button:", self._btn)
        for w in (self._x, self._y, self._count, self._interval):
            w.valueChanged.connect(self._emit)
        self._btn.currentTextChanged.connect(self._emit)

    def _populate(self, action):
        self._x.setValue(action.x)
        self._y.setValue(action.y)
        self._count.setValue(action.count)
        self._interval.setValue(action.interval)
        self._btn.setCurrentText(action.button)

    def _apply(self, action):
        action.x = self._x.value()
        action.y = self._y.value()
        action.count = self._count.value()
        action.interval = self._interval.value()
        action.button = self._btn.currentText()


class _MoveCursorOptions(_BaseOptions):
    def __init__(self, parent=None):
        super().__init__(parent)
        form = QFormLayout(self)
        form.setContentsMargins(8, 8, 8, 8)
        self._end_x = _coord_spin()
        self._end_y = _coord_spin()
        self._dur = _dur_spin(0.0, 60.0)
        self._use_start = QCheckBox("Custom start position")
        self._start_x = _coord_spin()
        self._start_x.setEnabled(False)
        self._start_y = _coord_spin()
        self._start_y.setEnabled(False)
        pick_end_btn = QPushButton("Pick end position")
        pick_end_btn.clicked.connect(lambda: self._start_pick(
            lambda x, y: (self._end_x.setValue(x), self._end_y.setValue(y))
        ))
        pick_start_btn = QPushButton("Pick start position")
        pick_start_btn.clicked.connect(lambda: self._start_pick(
            lambda x, y: (self._start_x.setValue(x), self._start_y.setValue(y))
        ))
        form.addRow("End X:", self._end_x)
        form.addRow("End Y:", self._end_y)
        form.addRow("", pick_end_btn)
        form.addRow("Duration (s):", self._dur)
        form.addRow("", self._use_start)
        form.addRow("Start X:", self._start_x)
        form.addRow("Start Y:", self._start_y)
        form.addRow("", pick_start_btn)
        self._use_start.toggled.connect(self._start_x.setEnabled)
        self._use_start.toggled.connect(self._start_y.setEnabled)
        self._use_start.toggled.connect(pick_start_btn.setEnabled)
        pick_start_btn.setEnabled(False)
        for w in (self._end_x, self._end_y, self._dur, self._start_x, self._start_y):
            w.valueChanged.connect(self._emit)
        self._use_start.toggled.connect(self._emit)

    def _populate(self, action):
        self._end_x.setValue(action.end_x)
        self._end_y.setValue(action.end_y)
        self._dur.setValue(action.duration)
        has_start = action.start_x is not None
        self._use_start.setChecked(has_start)
        if has_start:
            self._start_x.setValue(action.start_x)
            self._start_y.setValue(action.start_y)

    def _apply(self, action):
        action.end_x = self._end_x.value()
        action.end_y = self._end_y.value()
        action.duration = self._dur.value()
        if self._use_start.isChecked():
            action.start_x = self._start_x.value()
            action.start_y = self._start_y.value()
        else:
            action.start_x = None
            action.start_y = None


class _ClickDragOptions(_BaseOptions):
    def __init__(self, parent=None):
        super().__init__(parent)
        form = QFormLayout(self)
        form.setContentsMargins(8, 8, 8, 8)
        self._end_x = _coord_spin()
        self._end_y = _coord_spin()
        self._dur = _dur_spin(0.0, 60.0)
        self._btn = _button_combo()
        self._use_start = QCheckBox("Custom start position")
        self._start_x = _coord_spin()
        self._start_x.setEnabled(False)
        self._start_y = _coord_spin()
        self._start_y.setEnabled(False)
        pick_end_btn = QPushButton("Pick end position")
        pick_end_btn.clicked.connect(lambda: self._start_pick(
            lambda x, y: (self._end_x.setValue(x), self._end_y.setValue(y))
        ))
        pick_start_btn = QPushButton("Pick start position")
        pick_start_btn.clicked.connect(lambda: self._start_pick(
            lambda x, y: (self._start_x.setValue(x), self._start_y.setValue(y))
        ))
        form.addRow("End X:", self._end_x)
        form.addRow("End Y:", self._end_y)
        form.addRow("", pick_end_btn)
        form.addRow("Duration (s):", self._dur)
        form.addRow("Button:", self._btn)
        form.addRow("", self._use_start)
        form.addRow("Start X:", self._start_x)
        form.addRow("Start Y:", self._start_y)
        form.addRow("", pick_start_btn)
        self._use_start.toggled.connect(self._start_x.setEnabled)
        self._use_start.toggled.connect(self._start_y.setEnabled)
        self._use_start.toggled.connect(pick_start_btn.setEnabled)
        pick_start_btn.setEnabled(False)
        for w in (self._end_x, self._end_y, self._dur, self._start_x, self._start_y):
            w.valueChanged.connect(self._emit)
        self._btn.currentTextChanged.connect(self._emit)
        self._use_start.toggled.connect(self._emit)

    def _populate(self, action):
        self._end_x.setValue(action.end_x)
        self._end_y.setValue(action.end_y)
        self._dur.setValue(action.duration)
        self._btn.setCurrentText(action.button)
        has_start = action.start_x is not None
        self._use_start.setChecked(has_start)
        if has_start:
            self._start_x.setValue(action.start_x)
            self._start_y.setValue(action.start_y)

    def _apply(self, action):
        action.end_x = self._end_x.value()
        action.end_y = self._end_y.value()
        action.duration = self._dur.value()
        action.button = self._btn.currentText()
        if self._use_start.isChecked():
            action.start_x = self._start_x.value()
            action.start_y = self._start_y.value()
        else:
            action.start_x = None
            action.start_y = None


class _WaitOptions(_BaseOptions):
    def __init__(self, parent=None):
        super().__init__(parent)
        form = QFormLayout(self)
        form.setContentsMargins(8, 8, 8, 8)
        self._seconds = _dur_spin(0.01, 3600.0)
        self._seconds.setSingleStep(0.5)
        form.addRow("Seconds:", self._seconds)
        self._seconds.valueChanged.connect(self._emit)

    def _populate(self, action):
        self._seconds.setValue(action.seconds)

    def _apply(self, action):
        action.seconds = self._seconds.value()


class _PressKeyOptions(_BaseOptions):
    def __init__(self, parent=None):
        super().__init__(parent)
        form = QFormLayout(self)
        form.setContentsMargins(8, 8, 8, 8)
        self._key = QLineEdit()
        self._key.setPlaceholderText("e.g. enter, f5, a")
        form.addRow("Key:", self._key)
        self._key.textChanged.connect(self._emit)

    def _populate(self, action):
        self._key.setText(action.key)

    def _apply(self, action):
        action.key = self._key.text()


class _HotkeyOptions(_BaseOptions):
    def __init__(self, parent=None):
        super().__init__(parent)
        form = QFormLayout(self)
        form.setContentsMargins(8, 8, 8, 8)
        self._keys = QLineEdit()
        self._keys.setPlaceholderText("e.g. ctrl, c")
        form.addRow("Keys:", self._keys)
        self._keys.textChanged.connect(self._emit)

    def _populate(self, action):
        self._keys.setText(", ".join(action.keys))

    def _apply(self, action):
        action.keys = [k.strip() for k in self._keys.text().split(",") if k.strip()]


class _TypeTextOptions(_BaseOptions):
    def __init__(self, parent=None):
        super().__init__(parent)
        form = QFormLayout(self)
        form.setContentsMargins(8, 8, 8, 8)
        self._text = QLineEdit()
        self._interval = _dur_spin(0.01, 1.0)
        self._interval.setSingleStep(0.05)
        form.addRow("Text:", self._text)
        form.addRow("Interval (s):", self._interval)
        self._text.textChanged.connect(self._emit)
        self._interval.valueChanged.connect(self._emit)

    def _populate(self, action):
        self._text.setText(action.text)
        self._interval.setValue(action.interval)

    def _apply(self, action):
        action.text = self._text.text()
        action.interval = self._interval.value()


class _HoldKeyOptions(_BaseOptions):
    def __init__(self, parent=None):
        super().__init__(parent)
        form = QFormLayout(self)
        form.setContentsMargins(8, 8, 8, 8)
        self._key = QLineEdit()
        self._key.setPlaceholderText("e.g. shift, w, space")
        self._dur = _dur_spin(0.1, 3600.0)
        form.addRow("Key:", self._key)
        form.addRow("Duration (s):", self._dur)
        self._key.textChanged.connect(self._emit)
        self._dur.valueChanged.connect(self._emit)

    def _populate(self, action):
        self._key.setText(action.key)
        self._dur.setValue(action.duration)

    def _apply(self, action):
        action.key = self._key.text()
        action.duration = self._dur.value()


# --- panel ---

class OptionsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_item = None

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 10, 0, 0)
        outer_layout.setSpacing(0)

        label = QLabel("Options")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)

        self._stack = QStackedWidget()
        self._blank = QWidget()

        self._widgets: dict[str, _BaseOptions] = {
            "Click":       _ClickOptions(),
            "RepeatClick": _RepeatClickOptions(),
            "MoveCursor":  _MoveCursorOptions(),
            "ClickDrag":   _ClickDragOptions(),
            "Wait":        _WaitOptions(),
            "PressKey":    _PressKeyOptions(),
            "Hotkey":      _HotkeyOptions(),
            "TypeText":    _TypeTextOptions(),
            "HoldKey":     _HoldKeyOptions(),
        }

        self._stack.addWidget(self._blank)
        for w in self._widgets.values():
            self._stack.addWidget(w)
            w.changed.connect(self._on_changed)

        outer_layout.addWidget(label)
        outer_layout.addWidget(line)
        outer_layout.addWidget(self._stack, 1)

    def show_for(self, macro_item):
        self._current_item = macro_item
        if macro_item is None:
            self._stack.setCurrentWidget(self._blank)
            return
        action = macro_item.action
        action_type = action.to_dict().get("Type", "")
        widget = self._widgets.get(action_type)
        if widget:
            widget.load(action)
            self._stack.setCurrentWidget(widget)
        else:
            self._stack.setCurrentWidget(self._blank)

    def _on_changed(self):
        if self._current_item is not None:
            self._current_item.refresh()
            self._current_item.mark_configured()
