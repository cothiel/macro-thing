from pynput import mouse, keyboard
from pynput.keyboard import Key
import time

_RECORD_HOTKEY = Key.f9


class MacroRecorder:
    def __init__(self, on_complete=None):
        self._mouse_listener = mouse.Listener(
            on_move=self._on_move,
            on_click=self._on_click,
            on_scroll=self._on_scroll,
        )
        self._keyboard_listener = keyboard.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release,
        )
        self._events = []
        self._start_time = None

    def start(self):
        self._events = []
        self._start_time = time.monotonic()
        self._mouse_listener.start()
        self._keyboard_listener.start()

    def stop(self):
        self._mouse_listener.stop()
        self._keyboard_listener.stop()
        self._mouse_listener.join()
        self._keyboard_listener.join()

    def get_events(self):
        """Return a copy of all recorded events."""
        return list(self._events)

    def _ts(self):
        return time.monotonic() - self._start_time  # type: ignore[operator]  # always set before listeners fire

    def _on_move(self, x, y):
        self._events.append({"type": "mouse_move", "x": x, "y": y, "timestamp": self._ts()})

    def _on_click(self, x, y, button, pressed):
        self._events.append({
            "type": "mouse_button",
            "x": x,
            "y": y,
            "button": button.name,   # 'left', 'right', 'middle'
            "pressed": pressed,
            "timestamp": self._ts(),
        })

    def _on_scroll(self, x, y, dx, dy):
        self._events.append({
            "type": "mouse_scroll",
            "x": x,
            "y": y,
            "dx": dx,
            "dy": dy,
            "timestamp": self._ts(),
        })

    def _on_key_press(self, key):
        if key == _RECORD_HOTKEY:
            return
        self._events.append({"type": "key_press", "key": _normalize_key(key), "timestamp": self._ts()})

    def _on_key_release(self, key):
        if key == _RECORD_HOTKEY:
            return
        self._events.append({"type": "key_release", "key": _normalize_key(key), "timestamp": self._ts()})


def _normalize_key(key):
    """Return a stable string name for a pynput key, suitable for pyautogui translation."""
    if hasattr(key, 'char') and key.char is not None:
        return key.char          # printable character, e.g. 'a', '1', '!'
    if hasattr(key, 'name'):
        return key.name          # special key name, e.g. 'enter', 'shift', 'ctrl_l'
    return str(key)
