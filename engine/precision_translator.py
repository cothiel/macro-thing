from engine.actions import (
    ClickAction, MoveCursorAction, ClickDragAction,
    WaitAction, PressKeyAction, HoldKeyAction, HotkeyAction, ScrollAction,
)

# Minimum gap (seconds) between non-move events before a WaitAction is inserted.
_WAIT_THRESHOLD = 0.05

# Key held longer than this becomes HoldKeyAction; shorter becomes PressKeyAction.
_HOLD_THRESHOLD = 0.15

# pynput key name → pyautogui key string for names that differ.
_KEY_MAP = {
    "ctrl_l":      "ctrlleft",
    "ctrl_r":      "ctrlright",
    "shift_l":     "shiftleft",
    "shift_r":     "shiftright",
    "alt_l":       "altleft",
    "alt_r":       "altright",
    "alt_gr":      "altright",
    "cmd":         "winleft",
    "cmd_l":       "winleft",
    "cmd_r":       "winright",
    "caps_lock":   "capslock",
    "num_lock":    "numlock",
    "scroll_lock": "scrolllock",
    "print_screen":"printscreen",
    "page_up":     "pageup",
    "page_down":   "pagedown",
    "menu":        "apps",
}


def _pyautogui_key(key: str) -> str:
    return _KEY_MAP.get(key, key)


def translate_precision(events: list) -> list:
    """
    Convert a flat list of raw recorder event dicts into a list of BaseAction objects.
    Every pynput event maps to its closest pyautogui action:
      mouse_move           → MoveCursorAction  (gap between events used as duration)
      mouse_button press+release (no moves between) → ClickAction
      mouse_button press+release (moves between)    → ClickDragAction
      mouse_scroll         → ScrollAction
      key_press+release (short hold)  → PressKeyAction
      key_press+release (long hold)   → HoldKeyAction
      overlapping key_presses (chord) → HotkeyAction
    WaitAction is inserted before non-move events when the gap exceeds _WAIT_THRESHOLD.
    """
    actions = []
    prev_ts = 0.0
    i = 0
    n = len(events)

    while i < n:
        ev = events[i]
        gap = ev["timestamp"] - prev_ts

        # --- mouse move ---
        if ev["type"] == "mouse_move":
            # A gap this large means the mouse was stationary (pynput only
            # fires on_move when the cursor actually changes position), not
            # that the user dragged slowly -- replay it as an explicit pause
            # followed by an instant jump, not a slow glide across the screen.
            duration = round(max(0.0, gap), 4)
            if duration > _WAIT_THRESHOLD:
                actions.append(WaitAction(duration))
                duration = 0.0
            actions.append(MoveCursorAction(ev["x"], ev["y"], duration=duration))
            prev_ts = ev["timestamp"]
            i += 1

        # --- mouse button press ---
        elif ev["type"] == "mouse_button" and ev["pressed"]:
            if gap > _WAIT_THRESHOLD:
                actions.append(WaitAction(round(gap, 3)))

            release_idx = _find_mouse_release(events, i, ev["button"])
            if release_idx == -1:
                # No matching release in the recording; skip the press.
                prev_ts = ev["timestamp"]
                i += 1
                continue

            moves_between = any(
                e["type"] == "mouse_move"
                for e in events[i + 1 : release_idx]
            )
            release_ev = events[release_idx]

            if moves_between:
                duration = round(release_ev["timestamp"] - ev["timestamp"], 3)
                actions.append(ClickDragAction(
                    end_x=release_ev["x"],
                    end_y=release_ev["y"],
                    duration=duration,
                    button=ev["button"],
                    start_x=ev["x"],
                    start_y=ev["y"],
                ))
            else:
                actions.append(ClickAction(ev["x"], ev["y"], button=ev["button"]))

            prev_ts = release_ev["timestamp"]
            i = release_idx + 1

        # --- orphaned mouse button release ---
        elif ev["type"] == "mouse_button" and not ev["pressed"]:
            i += 1

        # --- mouse scroll ---
        elif ev["type"] == "mouse_scroll":
            if gap > _WAIT_THRESHOLD:
                actions.append(WaitAction(round(gap, 3)))
            actions.append(ScrollAction(ev["x"], ev["y"], ev["dy"], ev["dx"]))
            prev_ts = ev["timestamp"]
            i += 1

        # --- key press ---
        elif ev["type"] == "key_press":
            if gap > _WAIT_THRESHOLD:
                actions.append(WaitAction(round(gap, 3)))

            chord_keys, chord_end = _collect_chord(events, i)

            if len(chord_keys) > 1 and chord_end != -1:
                # Multiple keys pressed before any were released → hotkey chord.
                actions.append(HotkeyAction([_pyautogui_key(k) for k in chord_keys]))
                prev_ts = events[chord_end]["timestamp"]
                i = chord_end + 1
            else:
                key = ev["key"]
                release_idx = _find_key_release(events, i, key)
                if release_idx == -1:
                    prev_ts = ev["timestamp"]
                    i += 1
                    continue

                duration = events[release_idx]["timestamp"] - ev["timestamp"]
                pykey = _pyautogui_key(key)
                if duration >= _HOLD_THRESHOLD:
                    actions.append(HoldKeyAction(pykey, round(duration, 3)))
                else:
                    actions.append(PressKeyAction(pykey))

                prev_ts = events[release_idx]["timestamp"]
                i = release_idx + 1

        # --- orphaned key release ---
        elif ev["type"] == "key_release":
            i += 1

        else:
            i += 1

    return actions


def _find_mouse_release(events, press_idx, button):
    for j in range(press_idx + 1, len(events)):
        ev = events[j]
        if ev["type"] == "mouse_button" and not ev["pressed"] and ev["button"] == button:
            return j
    return -1


def _find_key_release(events, press_idx, key):
    for j in range(press_idx + 1, len(events)):
        ev = events[j]
        if ev["type"] == "key_release" and ev["key"] == key:
            return j
    return -1


def _collect_chord(events, start_idx):
    """
    Starting from a key_press at start_idx, collect all additional key_presses
    that occur before any of the already-pressed keys are released (i.e. a chord).
    Returns (ordered_key_list, index_of_last_release).
    If no chord is detected, returns ([single_key], -1).
    """
    pressed = [events[start_idx]["key"]]
    j = start_idx + 1
    n = len(events)

    # Accumulate additional key presses until a release of one of ours is seen.
    while j < n:
        ev = events[j]
        if ev["type"] == "key_press":
            pressed.append(ev["key"])
            j += 1
        elif ev["type"] == "key_release" and ev["key"] in pressed:
            break
        else:
            j += 1

    if len(pressed) == 1:
        return pressed, -1

    # Find the release events for every key in the chord.
    remaining = set(pressed)
    last_release_idx = -1
    while j < n and remaining:
        ev = events[j]
        if ev["type"] == "key_release" and ev["key"] in remaining:
            remaining.discard(ev["key"])
            last_release_idx = j
        j += 1

    return pressed, last_release_idx
