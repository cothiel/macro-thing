import time

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QFrame, QStackedWidget,
    QFormLayout, QSpinBox, QDoubleSpinBox, QLineEdit, QComboBox, QCheckBox,
    QPushButton, QApplication,
)
from PySide6.QtCore import Qt, Signal, QPoint, QTimer, QEvent
from PySide6.QtGui import QPainter, QPen, QColor, QPolygon

from engine.actions import MoveCursorAction, ScrollAction
from engine.precision_translator import build_move_path


# --- key conversion ---

_QT_KEY_TO_PYAUTOGUI = {
    Qt.Key.Key_Return:       'enter',
    Qt.Key.Key_Enter:        'enter',
    Qt.Key.Key_Backspace:    'backspace',
    Qt.Key.Key_Delete:       'delete',
    Qt.Key.Key_Tab:          'tab',
    Qt.Key.Key_Escape:       'escape',
    Qt.Key.Key_Space:        'space',
    Qt.Key.Key_Up:           'up',
    Qt.Key.Key_Down:         'down',
    Qt.Key.Key_Left:         'left',
    Qt.Key.Key_Right:        'right',
    Qt.Key.Key_Home:         'home',
    Qt.Key.Key_End:          'end',
    Qt.Key.Key_PageUp:       'pageup',
    Qt.Key.Key_PageDown:     'pagedown',
    Qt.Key.Key_Insert:       'insert',
    Qt.Key.Key_CapsLock:     'capslock',
    Qt.Key.Key_NumLock:      'numlock',
    Qt.Key.Key_ScrollLock:   'scrolllock',
    Qt.Key.Key_Pause:        'pause',
    Qt.Key.Key_Print:        'printscreen',
    Qt.Key.Key_Shift:        'shift',
    Qt.Key.Key_Control:      'ctrl',
    Qt.Key.Key_Alt:          'alt',
    Qt.Key.Key_Meta:         'win',
    Qt.Key.Key_F1:  'f1',  Qt.Key.Key_F2:  'f2',  Qt.Key.Key_F3:  'f3',
    Qt.Key.Key_F4:  'f4',  Qt.Key.Key_F5:  'f5',  Qt.Key.Key_F6:  'f6',
    Qt.Key.Key_F7:  'f7',  Qt.Key.Key_F8:  'f8',  Qt.Key.Key_F9:  'f9',
    Qt.Key.Key_F10: 'f10', Qt.Key.Key_F11: 'f11', Qt.Key.Key_F12: 'f12',
    Qt.Key.Key_F13: 'f13', Qt.Key.Key_F14: 'f14', Qt.Key.Key_F15: 'f15',
    Qt.Key.Key_F16: 'f16', Qt.Key.Key_F17: 'f17', Qt.Key.Key_F18: 'f18',
    Qt.Key.Key_F19: 'f19', Qt.Key.Key_F20: 'f20', Qt.Key.Key_F21: 'f21',
    Qt.Key.Key_F22: 'f22', Qt.Key.Key_F23: 'f23', Qt.Key.Key_F24: 'f24',
}

def _qt_key_to_pyautogui(key: Qt.Key, text: str) -> str:
    """Returns a pyautogui key name for the given Qt key, or '' if unsupported."""
    if key in _QT_KEY_TO_PYAUTOGUI:
        return _QT_KEY_TO_PYAUTOGUI[key]
    # Derive letters/digits from the key CODE, not text: when a modifier like
    # Ctrl is held, event.text() is the control character (e.g. '\x03' for
    # Ctrl+C), not 'c', so the text path below fails for exactly the combos
    # people care about. This mirrors how HotkeysDialog maps keys.
    if Qt.Key.Key_A <= key <= Qt.Key.Key_Z:
        return chr(key).lower()
    if Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
        return chr(key)
    if text and text.isprintable() and len(text) == 1:
        return text.lower()
    return ''


_STANDALONE_MODIFIERS = (
    Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt,
    Qt.Key.Key_Meta, Qt.Key.Key_AltGr,
)


def _qt_combo_to_pyautogui_keys(event) -> list:
    """Capture a full hotkey combo (held modifiers + the key that completes
    it) from a single Qt key-press event, the same way HotkeysDialog
    captures a global hotkey -- Qt already reports currently-held
    modifiers via event.modifiers() on the event for the final key, so a
    chord like Ctrl+Shift+C arrives as one event for 'C' with both
    modifiers set, no separate press-then-press-then-press tracking needed.
    Returns a pyautogui-compatible key list (e.g. ['ctrl', 'shift', 'c']),
    or None while only a standalone modifier has been pressed so far (still
    waiting for the real key) or for an unsupported key.
    """
    if event.key() in _STANDALONE_MODIFIERS:
        return None

    keys = []
    mods = event.modifiers()
    if mods & Qt.KeyboardModifier.ControlModifier:
        keys.append('ctrl')
    if mods & Qt.KeyboardModifier.AltModifier:
        keys.append('alt')
    if mods & Qt.KeyboardModifier.ShiftModifier:
        keys.append('shift')
    if mods & Qt.KeyboardModifier.MetaModifier:
        keys.append('win')

    main_key = _qt_key_to_pyautogui(event.key(), event.text())
    if not main_key or main_key in keys:
        return None
    keys.append(main_key)
    return keys


class _KeyCaptureButton(QPushButton):
    """Inline key/hotkey recorder: click it and its label becomes 'Press a
    key...', then the next key (or modifier+key combo) you press is
    captured -- the same visible flow as the Settings -> Hotkeys buttons,
    with no popup.

    Capture is done with an application-level event filter rather than the
    widget's own keyPressEvent. The options panel this lives in is a docked
    child widget, not a top-level window, so it can't reliably hold the
    keyboard focus that keyPressEvent depends on (that's why the earlier
    focus-based attempts failed). An app-level filter intercepts the
    keypress regardless of which widget currently has focus."""
    captured = Signal(list)           # pyautogui key list, e.g. ['ctrl', 'c']
    capturing_changed = Signal(bool)  # so the app can pause its global hotkey listener meanwhile

    def __init__(self, combo: bool, idle_text: str, parent=None):
        super().__init__(parent)
        self._combo = combo
        self._idle_text = idle_text
        self._capturing = False
        self.clicked.connect(self._begin_capture)

    def set_idle_text(self, text: str):
        self._idle_text = text
        if not self._capturing:
            self.setText(text)

    def _begin_capture(self):
        if self._capturing:
            return
        self._capturing = True
        self.setText("Press a key combo..." if self._combo else "Press a key...")
        self.capturing_changed.emit(True)
        QApplication.instance().installEventFilter(self)

    def _end_capture(self):
        if not self._capturing:
            return
        self._capturing = False
        QApplication.instance().removeEventFilter(self)
        self.setText(self._idle_text)
        self.capturing_changed.emit(False)

    def eventFilter(self, obj, event):
        if not self._capturing:
            return super().eventFilter(obj, event)
        etype = event.type()
        if etype == QEvent.Type.ShortcutOverride:
            # Before delivering a modifier+key combo as a normal KeyPress, Qt
            # first sends a ShortcutOverride. If that combo collides with any
            # shortcut in the app, the KeyPress is consumed as a shortcut and
            # never reaches this filter -- which is why some combos (e.g.
            # ctrl+shift+home) were silently failing while others worked.
            # Accepting it forces Qt to deliver a plain KeyPress instead.
            event.accept()
            return True
        if etype == QEvent.Type.KeyRelease:
            return True  # swallow releases so they don't leak into the app
        if etype != QEvent.Type.KeyPress:
            return super().eventFilter(obj, event)

        key = event.key()
        if key == Qt.Key.Key_Escape:
            self._end_capture()
            return True

        if self._combo:
            result = _qt_combo_to_pyautogui_keys(event)
        elif key in _STANDALONE_MODIFIERS:
            result = None  # a lone modifier isn't a complete key; keep waiting
        else:
            single = _qt_key_to_pyautogui(key, event.text())
            result = [single] if single else None

        if result:
            self._end_capture()
            self.captured.emit(result)
        return True  # swallow every keypress while capturing


# --- helpers ---

def _coord_spin() -> QSpinBox:
    s = QSpinBox()
    s.setRange(0, 7680)
    s.setToolTip("Absolute screen pixel coordinate (0, 0 is the top-left corner).")
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
    c.setToolTip("Mouse button to use.")
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


# --- path draw overlay ---

def _abs_to_local(widget, abs_x, abs_y) -> QPoint:
    """Map an absolute physical-pixel screen coordinate (as stored on a
    MoveCursorAction) to `widget`'s local coordinate space -- the inverse of
    the abs_x/abs_y computation in _PathDrawOverlay._screen_point(). Shared
    by _PathDrawOverlay (drawing the previous path as reference while
    redrawing) and the standalone path preview (drawing a group's existing
    path with no redraw involved)."""
    ratio = QApplication.primaryScreen().devicePixelRatio()
    return widget.mapFromGlobal(QPoint(round(abs_x / ratio), round(abs_y / ratio)))


class _PathPaintLayer(QWidget):
    """Pure visual layer, stacked on top of _PathDrawOverlay for rendering
    only. WA_TransparentForMouseEvents (WS_EX_TRANSPARENT on Windows) is the
    OS-sanctioned way to make a window truly click-through, so this widget
    can never be the thing letting clicks reach whatever's underneath --
    that's what a per-pixel-transparent *interactive* window risks doing,
    which is why all real input capture stays on the separate
    _PathDrawOverlay window using the same proven bulk-opacity trick as
    _ScreenPicker instead."""

    _PREVIOUS_COLOR = QColor(255, 255, 255, 130)
    _LIVE_COLOR = QColor("#0078d4")

    def __init__(self, geometry):
        _flags = (Qt.WindowType.FramelessWindowHint |
                  Qt.WindowType.WindowStaysOnTopHint |
                  Qt.WindowType.Tool)
        super().__init__(None, _flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setGeometry(geometry)
        self.previous_points = []   # QPoint, local coords
        self.live_points = []       # QPoint, local coords

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if len(self.previous_points) >= 2:
            pen = QPen(self._PREVIOUS_COLOR)
            pen.setWidth(2)
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawPolyline(QPolygon(self.previous_points))

        if len(self.live_points) >= 2:
            pen = QPen(self._LIVE_COLOR)
            pen.setWidth(3)
            painter.setPen(pen)
            painter.drawPolyline(QPolygon(self.live_points))

        if self.live_points:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self._LIVE_COLOR)
            painter.drawEllipse(self.live_points[-1], 5, 5)


class _PathDrawOverlay(QWidget):
    """Same always-on-top capture surface as _ScreenPicker (whole-window
    near-zero opacity, not per-pixel transparency -- that's what proved
    reliable at blocking clicks from reaching whatever's underneath), but
    records a dragged path instead of a single click. A separate
    _PathPaintLayer window, stacked on top and explicitly click-through,
    renders the path live without affecting input capture at all. Sampling
    is scoped strictly to the press-to-release window -- nothing is
    captured before the button goes down or after it comes back up, and no
    other input (keys, other buttons) is ever recorded, only (x, y, time)
    while dragging."""
    path_drawn = Signal(list)   # list of (x, y, elapsed_seconds) tuples
    cancelled = Signal()

    def __init__(self, previous_points=None):
        _flags = (Qt.WindowType.FramelessWindowHint |
                  Qt.WindowType.WindowStaysOnTopHint)
        super().__init__(None, _flags)
        self.setWindowOpacity(0.01)
        self.setCursor(Qt.CursorShape.CrossCursor)
        geometry = QApplication.primaryScreen().virtualGeometry()
        self.setGeometry(geometry)

        self._hint = QLabel(
            "  Click and hold to draw a path, release to finish  |  Esc to cancel  \n"
            "  White dashed = previous path   Blue = new path  "
        )
        self._hint.setWindowFlags(_flags | Qt.WindowType.Tool)
        self._hint.setStyleSheet(
            "background:#1e1e1e; color:white; padding:8px 14px;"
            "border-radius:4px; font-size:13px;"
        )
        self._hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hint.adjustSize()
        sr = QApplication.primaryScreen().geometry()
        self._hint.move(sr.center().x() - self._hint.width() // 2, 20)
        self._hint.show()

        self._drawing = False
        self._start_time = 0.0
        self._samples = []   # (x, y, elapsed_seconds) in absolute screen coords -- the real data

        self._paint_layer = _PathPaintLayer(geometry)
        self._paint_layer.previous_points = [_abs_to_local(self, x, y) for x, y in (previous_points or [])]
        self._paint_layer.show()

        self.show()
        self.activateWindow()
        self.setFocus()
        # Explicit OS-level grabs, on top of activation, to guarantee Esc
        # is caught instantly rather than depending on focus/activation
        # timing being exactly right.
        self.grabMouse()
        self.grabKeyboard()

    def closeEvent(self, event):
        self.releaseKeyboard()
        self.releaseMouse()
        self._paint_layer.close()
        self._hint.close()
        super().closeEvent(event)

    def _screen_point(self, event):
        pos = event.globalPosition().toPoint()
        screen = QApplication.screenAt(pos)
        ratio = screen.devicePixelRatio() if screen else 1.0
        return round(pos.x() * ratio), round(pos.y() * ratio)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drawing = True
            self._start_time = time.monotonic()
            x, y = self._screen_point(event)
            self._samples = [(x, y, 0.0)]
            self._paint_layer.live_points = [event.position().toPoint()]
            self._paint_layer.update()
        elif event.button() == Qt.MouseButton.RightButton:
            self.cancelled.emit()
            self.close()

    def mouseMoveEvent(self, event):
        if not self._drawing:
            return
        x, y = self._screen_point(event)
        self._samples.append((x, y, time.monotonic() - self._start_time))
        self._paint_layer.live_points.append(event.position().toPoint())
        self._paint_layer.update()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton or not self._drawing:
            return
        self._drawing = False
        if len(self._samples) >= 2:
            self.path_drawn.emit(self._samples)
        else:
            self.cancelled.emit()
        self.close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()
            self.close()


# --- base ---

class _BaseOptions(QWidget):
    changed = Signal()
    # Emitted by widgets that need to capture raw keyboard input (PressKey,
    # Hotkey) while the app's global hotkey listener -- a low-level,
    # OS-wide keyboard hook that runs the entire time the main window is
    # open -- could otherwise intercept the very keys being captured before
    # Qt ever sees them. MainWindow pauses that listener while this is True,
    # the same way it already does for the Hotkeys settings dialog.
    capturing_changed = Signal(bool)

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

    def _pick_position_button(self, label, on_picked) -> QPushButton:
        btn = QPushButton(label)
        btn.setToolTip("Click, then click anywhere on screen to capture that position.")
        btn.clicked.connect(lambda: self._start_pick(on_picked))
        return btn

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
        pick_btn = self._pick_position_button("Pick position",
            lambda x, y: (self._x.setValue(x), self._y.setValue(y))
        )
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
        self._count.setToolTip("Number of times to click.")
        self._interval = _dur_spin(0.01, 60.0)
        self._interval.setToolTip("Seconds to wait between each click.")
        self._btn = _button_combo()
        pick_btn = self._pick_position_button("Pick position",
            lambda x, y: (self._x.setValue(x), self._y.setValue(y))
        )
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
        self._dur.setToolTip(
            "Time to glide from the current position to the end position. "
            "0 jumps instantly; very short values still play back precisely, "
            "not just as a jump."
        )
        self._use_start = QCheckBox("Custom start position")
        self._use_start.setToolTip(
            "If enabled, the cursor jumps instantly to Start X/Y before gliding "
            "to the end position, instead of gliding from wherever it already is."
        )
        self._start_x = _coord_spin()
        self._start_x.setEnabled(False)
        self._start_y = _coord_spin()
        self._start_y.setEnabled(False)
        pick_end_btn = self._pick_position_button("Pick end position",
            lambda x, y: (self._end_x.setValue(x), self._end_y.setValue(y))
        )
        pick_start_btn = self._pick_position_button("Pick start position",
            lambda x, y: (self._start_x.setValue(x), self._start_y.setValue(y))
        )
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
        self._dur.setToolTip("Time to drag from the start position to the end position.")
        self._btn = _button_combo()
        self._btn.setToolTip("Mouse button held down for the duration of the drag.")
        self._use_start = QCheckBox("Custom start position")
        self._use_start.setToolTip(
            "If enabled, the cursor jumps instantly to Start X/Y before the drag "
            "begins, instead of starting from wherever it already is."
        )
        self._start_x = _coord_spin()
        self._start_x.setEnabled(False)
        self._start_y = _coord_spin()
        self._start_y.setEnabled(False)
        pick_end_btn = self._pick_position_button("Pick end position",
            lambda x, y: (self._end_x.setValue(x), self._end_y.setValue(y))
        )
        pick_start_btn = self._pick_position_button("Pick start position",
            lambda x, y: (self._start_x.setValue(x), self._start_y.setValue(y))
        )
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
        self._seconds.setToolTip("How long to pause before the next action runs.")
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
        self._key = _KeyCaptureButton(combo=False, idle_text="Click to select key")
        self._key.setToolTip("Click, then press the single key this action should send.")
        self._key.captured.connect(self._on_captured)
        self._key.capturing_changed.connect(self.capturing_changed)
        form.addRow("Key:", self._key)

    def _populate(self, action):
        self._key.set_idle_text(action.key)

    def _apply(self, action):
        action.key = self._key.text()

    def _on_captured(self, keys):
        self._key.set_idle_text(keys[0])
        self._emit()


class _HotkeyOptions(_BaseOptions):
    """Records a hotkey combo the same way Settings -> Hotkeys does: click,
    then press the actual key combination (hold modifiers + the final key
    together) instead of typing key names by hand."""

    def __init__(self, parent=None):
        super().__init__(parent)
        form = QFormLayout(self)
        form.setContentsMargins(8, 8, 8, 8)
        self._keys = []
        self._keys_btn = _KeyCaptureButton(combo=True, idle_text="Click to record hotkey")
        self._keys_btn.setToolTip(
            "Click, then press the key combination you want -- hold any "
            "modifiers and press the final key together, the same way as "
            "recording a hotkey in Settings -> Hotkeys. Keys are pressed "
            "down in the order shown, then released in reverse order."
        )
        self._keys_btn.captured.connect(self._on_captured)
        self._keys_btn.capturing_changed.connect(self.capturing_changed)
        form.addRow("Keys:", self._keys_btn)

    def _populate(self, action):
        self._keys = list(action.keys)
        self._update_label()

    def _apply(self, action):
        action.keys = list(self._keys)

    def _update_label(self):
        if self._keys:
            self._keys_btn.set_idle_text(" + ".join(k.capitalize() for k in self._keys))
        else:
            self._keys_btn.set_idle_text("Click to record hotkey")

    def _on_captured(self, keys):
        self._keys = keys
        self._update_label()
        self._emit()


class _TypeTextOptions(_BaseOptions):
    def __init__(self, parent=None):
        super().__init__(parent)
        form = QFormLayout(self)
        form.setContentsMargins(8, 8, 8, 8)
        self._text = QLineEdit()
        self._text.setToolTip("Text to type, one character at a time. Limited to printable ASCII characters.")
        self._interval = _dur_spin(0.01, 1.0)
        self._interval.setSingleStep(0.05)
        self._interval.setToolTip("Seconds between each keystroke.")
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


class _MoveGroupOptions(_BaseOptions):
    """Shown when a collapsed move-group MacroRow is selected. Read-only
    summary plus a single explicit 'Expand' action -- editing individual
    samples happens after expanding, not here (auto-expanding on every
    selection would reintroduce the wall-of-rows problem grouping solves)."""
    expand_clicked = Signal(object)
    path_redrawn = Signal(object, list)   # (row, new_actions)

    _PREVIEW_DURATION_MS = 2000

    def __init__(self, parent=None):
        super().__init__(parent)
        form = QFormLayout(self)
        form.setContentsMargins(8, 8, 8, 8)
        self._summary = QLabel()
        self._summary.setWordWrap(True)
        preview_btn = QPushButton("Preview path")
        preview_btn.setToolTip("Briefly show this path on-screen so you can see what it does.")
        preview_btn.clicked.connect(self._preview_path)
        draw_btn = QPushButton("Draw new path...")
        draw_btn.setToolTip("Click and hold on-screen to trace a new path; release to finish.")
        draw_btn.clicked.connect(self._start_draw)
        expand_btn = QPushButton("Expand into individual moves")
        expand_btn.setToolTip(
            "Splits this row back into one row per move sample, so you can "
            "edit or delete a single point without affecting the rest."
        )
        expand_btn.clicked.connect(lambda: self.expand_clicked.emit(self._action))
        form.addRow(self._summary)
        form.addRow(preview_btn)
        form.addRow(draw_btn)
        form.addRow(expand_btn)

    def _move_points(self, row):
        return [(a.end_x, a.end_y) for a in row.actions if isinstance(a, MoveCursorAction)]

    def _populate(self, row):
        first, last = row.actions[0], row.actions[-1]
        move_count = sum(1 for a in row.actions if isinstance(a, MoveCursorAction))
        pause_count = len(row.actions) - move_count
        total_duration = sum(
            a.duration if isinstance(a, MoveCursorAction) else a.seconds
            for a in row.actions
        )
        pause_note = f"\nIncludes {pause_count} short pause{'s' if pause_count != 1 else ''}" if pause_count else ""
        self._summary.setText(
            f"{move_count} move samples{pause_note}\n"
            f"({first.end_x}, {first.end_y}) -> ({last.end_x}, {last.end_y})\n"
            f"Total duration: {total_duration:.2f}s"
        )

    def _apply(self, row):
        pass  # no editable fields here; the buttons bypass _emit entirely

    def _preview_path(self):
        geometry = QApplication.primaryScreen().virtualGeometry()
        layer = _PathPaintLayer(geometry)
        layer.live_points = [_abs_to_local(layer, x, y) for x, y in self._move_points(self._action)]
        layer.show()
        self._preview_layer = layer   # keep a reference so it isn't GC'd before the timer fires
        QTimer.singleShot(self._PREVIEW_DURATION_MS, layer.close)

    def _start_draw(self):
        previous_points = self._move_points(self._action)
        self._overlay = _PathDrawOverlay(previous_points=previous_points)
        self._overlay.path_drawn.connect(self._on_path_drawn)

    def _on_path_drawn(self, samples):
        new_actions = build_move_path(samples)
        self.path_redrawn.emit(self._action, new_actions)


class _ScrollGroupOptions(_BaseOptions):
    """Shown when a collapsed scroll-group MacroRow is selected. Read-only
    summary plus 'Expand' -- unlike a move group, a scroll burst has no
    spatial path worth drawing or previewing, just a magnitude and pace."""
    expand_clicked = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        form = QFormLayout(self)
        form.setContentsMargins(8, 8, 8, 8)
        self._summary = QLabel()
        self._summary.setWordWrap(True)
        expand_btn = QPushButton("Expand into individual scrolls")
        expand_btn.setToolTip(
            "Splits this row back into one row per scroll notch, so you can "
            "edit or delete a single one without affecting the rest."
        )
        expand_btn.clicked.connect(lambda: self.expand_clicked.emit(self._action))
        form.addRow(self._summary)
        form.addRow(expand_btn)

    def _populate(self, row):
        scrolls = [a for a in row.actions if isinstance(a, ScrollAction)]
        pause_count = len(row.actions) - len(scrolls)
        total_dy = sum(a.dy for a in scrolls)
        total_dx = sum(a.dx for a in scrolls)
        total_duration = sum(
            a.duration if isinstance(a, ScrollAction) else a.seconds
            for a in row.actions
        )
        pause_note = f"\nIncludes {pause_count} short pause{'s' if pause_count != 1 else ''}" if pause_count else ""
        amount_line = f"Vertical: {total_dy:+d} notches"
        if total_dx:
            amount_line += f", Horizontal: {total_dx:+d} notches"
        self._summary.setText(
            f"{len(scrolls)} scroll notches{pause_note}\n"
            f"{amount_line}\n"
            f"Total duration: {total_duration:.2f}s"
        )

    def _apply(self, row):
        pass  # no editable fields here; the Expand button bypasses _emit entirely


class _HoldKeyOptions(_BaseOptions):
    def __init__(self, parent=None):
        super().__init__(parent)
        form = QFormLayout(self)
        form.setContentsMargins(8, 8, 8, 8)
        self._key = QLineEdit()
        self._key.setPlaceholderText("e.g. shift, w, space")
        self._key.setToolTip("Key name to hold down.")
        self._dur = _dur_spin(0.1, 3600.0)
        self._dur.setToolTip(
            "How long to hold the key down. Pausing playback won't release it "
            "early -- that would leave it stuck down until resumed, which "
            "would fire repeated keypresses in whatever's focused."
        )
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


class _ScrollOptions(_BaseOptions):
    def __init__(self, parent=None):
        super().__init__(parent)
        form = QFormLayout(self)
        form.setContentsMargins(8, 8, 8, 8)
        self._x = _coord_spin()
        self._y = _coord_spin()
        pick_btn = QPushButton("Pick position")
        pick_btn.clicked.connect(lambda: self._start_pick(
            lambda x, y: (self._x.setValue(x), self._y.setValue(y))
        ))
        self._dy = QSpinBox()
        self._dy.setRange(-100000, 100000)
        self._dy.setToolTip(
            "Vertical amount, in mouse-wheel notches (1 notch = 1 physical "
            "wheel click). Positive scrolls up, negative scrolls down."
        )
        self._dx = QSpinBox()
        self._dx.setRange(-100000, 100000)
        self._dx.setToolTip(
            "Horizontal amount, in mouse-wheel notches. Positive scrolls "
            "right, negative scrolls left."
        )
        self._duration = _dur_spin(0.0, 60.0)
        self._duration.setToolTip(
            "Time to spread the scroll over. 0 scrolls instantly in one motion."
        )
        self._speed = QSpinBox()
        self._speed.setRange(1, 100000)
        self._speed.setToolTip(
            "Notches sent per step while animating (only matters when "
            "duration > 0). Smaller feels smoother, larger feels choppier."
        )

        form.addRow("X:", self._x)
        form.addRow("Y:", self._y)
        form.addRow("", pick_btn)
        form.addRow("Amount (vertical):", self._dy)
        form.addRow("Amount (horizontal):", self._dx)
        form.addRow("Duration (s):", self._duration)
        form.addRow("Speed (notches/step):", self._speed)

        for w in (self._x, self._y, self._dy, self._dx, self._duration, self._speed):
            w.valueChanged.connect(self._emit)

    def _populate(self, action):
        self._x.setValue(action.x)
        self._y.setValue(action.y)
        self._dy.setValue(action.dy)
        self._dx.setValue(action.dx)
        self._duration.setValue(action.duration)
        self._speed.setValue(action.speed)

    def _apply(self, action):
        action.x = self._x.value()
        action.y = self._y.value()
        action.dy = self._dy.value()
        action.dx = self._dx.value()
        action.duration = self._duration.value()
        action.speed = self._speed.value()


# --- panel ---

class OptionsPanel(QWidget):
    row_changed = Signal(object)        # replaces direct macro_item.refresh()/mark_configured()
    expand_requested = Signal(object)   # user clicked "Expand" on a move-group row
    path_redrawn = Signal(object, list) # user drew a new path for a move-group row: (row, new_actions)
    capturing_changed = Signal(bool)    # a child widget started/stopped grabbing raw keyboard input

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_row = None

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
        self._move_group_widget = _MoveGroupOptions()
        self._scroll_group_widget = _ScrollGroupOptions()

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
            "Scroll":      _ScrollOptions(),
        }

        self._stack.addWidget(self._blank)
        self._stack.addWidget(self._move_group_widget)
        self._move_group_widget.expand_clicked.connect(self.expand_requested)
        self._move_group_widget.path_redrawn.connect(self.path_redrawn)
        self._stack.addWidget(self._scroll_group_widget)
        self._scroll_group_widget.expand_clicked.connect(self.expand_requested)
        for w in self._widgets.values():
            self._stack.addWidget(w)
            w.changed.connect(self._on_changed)
            w.capturing_changed.connect(self.capturing_changed)

        outer_layout.addWidget(label)
        outer_layout.addWidget(line)
        outer_layout.addWidget(self._stack, 1)

    def show_for(self, row):
        self._current_row = row
        if row is None:
            self._stack.setCurrentWidget(self._blank)
            return
        if row.is_group():
            if row.group_kind() is ScrollAction:
                self._scroll_group_widget.load(row)
                self._stack.setCurrentWidget(self._scroll_group_widget)
            else:
                self._move_group_widget.load(row)
                self._stack.setCurrentWidget(self._move_group_widget)
            return
        action = row.actions[0]
        action_type = action.to_dict().get("Type", "")
        widget = self._widgets.get(action_type)
        if widget:
            widget.load(action)
            self._stack.setCurrentWidget(widget)
        else:
            self._stack.setCurrentWidget(self._blank)

    def _on_changed(self):
        if self._current_row is not None:
            self._current_row.mark_configured()
            self.row_changed.emit(self._current_row)
