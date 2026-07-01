import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from engine.actions import BaseAction, MoveCursorAction


class MacroRow:
    """One editor row: either a single action, or a collapsed run of
    consecutive MoveCursorActions (a 'group')."""

    def __init__(self, actions: list, configured: bool = True):
        self.actions = actions
        self.configured = configured  # only meaningful when not is_group()

    def is_group(self) -> bool:
        return len(self.actions) > 1

    def label(self) -> str:
        if not self.is_group():
            return self.actions[0].to_dict().get("Type", "Action")
        last = self.actions[-1]
        return f"Move ({len(self.actions)}) -> ({last.end_x}, {last.end_y})"

    def is_configured(self) -> bool:
        return True if self.is_group() else self.configured

    def mark_configured(self):
        self.configured = True


def group_actions(actions: list) -> list:
    """Collapse runs of 2+ consecutive MoveCursorActions into one MacroRow
    each (configured=True -- everything here came from a completed
    recording, nothing needs 'filling in'). Every other action, and any
    lone MoveCursorAction, becomes its own 1-action MacroRow. Pure
    function; does not mutate input."""
    rows = []
    i = 0
    n = len(actions)
    while i < n:
        a = actions[i]
        if isinstance(a, MoveCursorAction):
            j = i
            while j < n and isinstance(actions[j], MoveCursorAction):
                j += 1
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
