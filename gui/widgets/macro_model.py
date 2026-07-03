import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from engine.actions import BaseAction, MoveCursorAction, ScrollAction, WaitAction

# Action types that group_actions() collapses runs of into a single MacroRow.
# A run is always homogeneous -- a burst of MoveCursorActions never merges
# with a burst of ScrollActions, only with more of its own kind (optionally
# across a short WaitAction, see group_actions).
_GROUPABLE_TYPES = (MoveCursorAction, ScrollAction)


class MacroRow:
    """One editor row: either a single action, or a collapsed run of
    consecutive same-type groupable actions (a 'group') -- optionally with
    short WaitActions folded in between bursts (see group_actions'
    merge_wait_threshold), in which case the group is a mix of the
    groupable type and WaitAction rather than purely the former."""

    def __init__(self, actions: list, configured: bool = True):
        self.actions = actions
        self.configured = configured  # only meaningful when not is_group()

    def is_group(self) -> bool:
        return len(self.actions) > 1

    def group_kind(self):
        """The groupable action type (MoveCursorAction or ScrollAction) this
        row is a run of, or None if this isn't a group. A run always starts
        on the groupable type itself (never a folded-in WaitAction), so the
        first action's type is authoritative."""
        return type(self.actions[0]) if self.is_group() else None

    def label(self) -> str:
        if not self.is_group():
            return self.actions[0].to_dict().get("Type", "Action")

        pause_count = sum(1 for a in self.actions if isinstance(a, WaitAction))
        suffix = f", {pause_count} pause{'s' if pause_count != 1 else ''}" if pause_count else ""
        kind = self.group_kind()

        if kind is ScrollAction:
            scrolls = [a for a in self.actions if isinstance(a, ScrollAction)]
            total_dy = sum(a.dy for a in scrolls)
            total_dx = sum(a.dx for a in scrolls)
            amount = f"dy={total_dy:+d}" + (f", dx={total_dx:+d}" if total_dx else "")
            return f"Scroll ({len(scrolls)}{suffix}) {amount}"

        move_count = len(self.actions) - pause_count
        last = self.actions[-1]
        return f"Move ({move_count}{suffix}) -> ({last.end_x}, {last.end_y})"

    def is_configured(self) -> bool:
        return True if self.is_group() else self.configured

    def mark_configured(self):
        self.configured = True


def group_actions(actions: list, merge_wait_threshold: float = 0.0) -> list:
    """Collapse runs of 2+ consecutive same-type groupable actions
    (MoveCursorAction or ScrollAction) into one MacroRow each
    (configured=True -- everything here came from a completed recording,
    nothing needs 'filling in'). Every other action, and any lone groupable
    action, becomes its own 1-action MacroRow. Pure function; does not
    mutate input.

    merge_wait_threshold: if > 0, a WaitAction of at most this many seconds
    that sits directly between two bursts of the same groupable type is
    folded into the same MacroRow as both bursts instead of splitting them
    into three separate rows -- a brief mid-gesture hesitation then reads as
    one row instead of fragmenting it, while a longer, more deliberate pause
    still gets its own visible row. This only changes how the same flat
    action list is split into editor rows; ungroup_rows() recovers the exact
    original list either way, so it never affects playback timing.
    """
    rows = []
    i = 0
    n = len(actions)
    while i < n:
        a = actions[i]
        a_type = type(a)
        if a_type in _GROUPABLE_TYPES:
            j = i
            while j < n and type(actions[j]) is a_type:
                j += 1
            # Keep absorbing a short-wait-then-same-type-burst pattern into
            # the same run for as long as it keeps matching (handles a chain
            # of several brief hesitations, not just one).
            while (
                merge_wait_threshold > 0
                and j < n and isinstance(actions[j], WaitAction)
                and actions[j].seconds <= merge_wait_threshold
                and j + 1 < n and type(actions[j + 1]) is a_type
            ):
                k = j + 1
                while k < n and type(actions[k]) is a_type:
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
