from engine.actions import (
    ClickAction, MoveCursorAction, ClickDragAction,
    WaitAction, PressKeyAction, HoldKeyAction, HotkeyAction, ScrollAction,
)

# Gap (seconds) above which a mouse-move's elapsed time gets promoted from
# the move's own `duration` field into an explicit WaitAction + instant jump
# instead. This is purely a display/grouping choice -- both paths already
# reproduce the gap's exact duration (see MoveCursorAction.execute()) -- so
# it can stay generous without costing any timing fidelity.
_MOVE_WAIT_THRESHOLD = 0.05

# Minimum gap (seconds) worth representing at all for click/key/scroll
# events. Unlike moves, these events have no field to silently absorb a
# sub-threshold gap into -- any gap this doesn't catch is simply dropped
# from playback entirely, so this stays just above floating-point/rounding
# noise rather than a "don't bother" cutoff.
_MIN_MEANINGFUL_GAP = 0.001

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


# Raw pynput key names for modifier keys. Overlapping key-press intervals are
# only ever treated as a deliberate hotkey chord when at least one of them is
# a modifier (matching how virtually every real shortcut is composed, e.g.
# ctrl+c, alt+tab). Plain letter/letter overlap is finger rollover from fast
# typing, not an intentional combo, and should stay individual key presses.
_MODIFIER_KEYS = {
    "ctrl", "ctrl_l", "ctrl_r",
    "shift", "shift_l", "shift_r",
    "alt", "alt_l", "alt_r", "alt_gr",
    "cmd", "cmd_l", "cmd_r",
}


def _is_modifier(key: str) -> bool:
    return key in _MODIFIER_KEYS


def _actions_for_move_sample(x, y, gap: float) -> list:
    """
    Shared by translate_precision's mouse_move handling and
    build_move_path(): a gap this large means the cursor was stationary
    (nothing fires while it isn't moving), so it's represented as an
    explicit pause followed by an instant jump rather than a slow glide;
    a small gap stays embedded in the move's own `duration` so it renders
    as part of the same collapsed group in the editor.
    """
    duration = round(max(0.0, gap), 4)
    if duration > _MOVE_WAIT_THRESHOLD:
        return [WaitAction(duration), MoveCursorAction(x, y, duration=0.0)]
    return [MoveCursorAction(x, y, duration=duration)]


def build_move_path(samples: list) -> list:
    """
    Convert a chronological list of (x, y, timestamp) samples -- e.g.
    captured while a user drags to redraw a move group's path -- into a
    list of BaseAction objects, using the same gap-preserving logic as a
    real recording. `timestamp` is seconds from an arbitrary common origin
    (e.g. time.monotonic() deltas); the first sample's own gap is ignored
    since there's nothing before it to wait on.
    """
    actions = []
    prev_ts = samples[0][2] if samples else 0.0
    for x, y, ts in samples:
        actions.extend(_actions_for_move_sample(x, y, ts - prev_ts))
        prev_ts = ts
    return actions


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
    WaitAction is inserted before click/key/scroll events whenever there's any
    meaningful gap, and before a move when that gap is large enough to be
    worth showing as its own row (see _MIN_MEANINGFUL_GAP / _MOVE_WAIT_THRESHOLD).
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
            actions.extend(_actions_for_move_sample(ev["x"], ev["y"], gap))
            prev_ts = ev["timestamp"]
            i += 1

        # --- mouse button press ---
        elif ev["type"] == "mouse_button" and ev["pressed"]:
            if gap > _MIN_MEANINGFUL_GAP:
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
            if gap > _MIN_MEANINGFUL_GAP:
                actions.append(WaitAction(round(gap, 3)))
            actions.append(ScrollAction(ev["x"], ev["y"], ev["dy"], ev["dx"]))
            prev_ts = ev["timestamp"]
            i += 1

        # --- key press ---
        elif ev["type"] == "key_press":
            if gap > _MIN_MEANINGFUL_GAP:
                actions.append(WaitAction(round(gap, 3)))

            chord_keys, chord_end = _collect_chord(events, i)
            is_chord = len(chord_keys) > 1 and chord_end != -1 and any(_is_modifier(k) for k in chord_keys)

            if is_chord:
                # Multiple keys held down together, and at least one is a
                # modifier -> a deliberate hotkey (e.g. ctrl+c).
                actions.append(HotkeyAction([_pyautogui_key(k) for k in chord_keys]))
                prev_ts = events[chord_end]["timestamp"]
                i = chord_end + 1
            else:
                # Either a lone key, or plain keys that briefly overlapped
                # from fast-typing finger rollover rather than a deliberate
                # chord -- treat this one as its own press/hold. Advance only
                # one event at a time (not to release_idx+1) so an
                # overlapping partner key's own press isn't skipped over and
                # silently dropped.
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
                i += 1

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
