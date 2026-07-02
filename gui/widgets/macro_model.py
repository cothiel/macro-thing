import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from engine.actions import BaseAction, MoveCursorAction, WaitAction


class MacroRow:
    """One editor row: either a single action, or a collapsed run of
    consecutive MoveCursorActions (a 'group') -- optionally with short
    WaitActions folded in between bursts (see group_actions'
    merge_wait_threshold), in which case the group is a mix of
    MoveCursorAction and WaitAction rather than purely the former."""

    def __init__(self, actions: list, configured: bool = True):
        self.actions = actions
        self.configured = configured  # only meaningful when not is_group()

    def is_group(self) -> bool:
        return len(self.actions) > 1

    def label(self) -> str:
        if not self.is_group():
            return self.actions[0].to_dict().get("Type", "Action")
        last = self.actions[-1]
        move_count = sum(1 for a in self.actions if isinstance(a, MoveCursorAction))
        pause_count = len(self.actions) - move_count
        suffix = f", {pause_count} pause{'s' if pause_count != 1 else ''}" if pause_count else ""
        return f"Move ({move_count}{suffix}) -> ({last.end_x}, {last.end_y})"

    def is_configured(self) -> bool:
        return True if self.is_group() else self.configured

    def mark_configured(self):
        self.configured = True


def group_actions(actions: list, merge_wait_threshold: float = 0.0) -> list:
    """Collapse runs of 2+ consecutive MoveCursorActions into one MacroRow
    each (configured=True -- everything here came from a completed
    recording, nothing needs 'filling in'). Every other action, and any
    lone MoveCursorAction, becomes its own 1-action MacroRow. Pure
    function; does not mutate input.

    merge_wait_threshold: if > 0, a WaitAction of at most this many seconds
    that sits directly between two move bursts is folded into the same
    MacroRow as both bursts instead of splitting them into three separate
    rows -- a brief mid-gesture hesitation then reads as one path instead
    of fragmenting it, while a longer, more deliberate pause still gets its
    own visible row. This only changes how the same flat action list is
    split into editor rows; ungroup_rows() recovers the exact original list
    either way, so it never affects playback timing.
    """
    rows = []
    i = 0
    n = len(actions)
    while i < n:
        a = actions[i]
        if isinstance(a, MoveCursorAction):
            j = i
            while j < n and isinstance(actions[j], MoveCursorAction):
                j += 1
            # Keep absorbing a short-wait-then-move-burst pattern into the
            # same run for as long as it keeps matching (handles a chain of
            # several brief hesitations, not just one).
            while (
                merge_wait_threshold > 0
                and j < n and isinstance(actions[j], WaitAction)
                and actions[j].seconds <= merge_wait_threshold
                and j + 1 < n and isinstance(actions[j + 1], MoveCursorAction)
            ):
                k = j + 1
                while k < n and isinstance(actions[k], MoveCursorAction):
                    k += 1
                j = k
            rows.append(MacroRow(actions[i:j], configured=True))
            i = j
        else:
            rows.append(MacroRow([a], configured=True))
            i += 1
    return rows


def ungroup_rows(rows: list) -> list:
    """Inverse of group_actions -- flattens back to the flat list
    MacroPlayer/get_actions() consume. ungroup_rows(group_actions(x)) == x."""
    out = []
    for row in rows:
        out.extend(row.actions)
    return out
