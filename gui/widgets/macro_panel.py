import sys
import os
import copy

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QFrame, QListView, QAbstractItemView,
    QStyledItemDelegate, QStyle,
)
from PySide6.QtCore import Qt, Signal, QAbstractListModel, QModelIndex, QMimeData, QRect, QSize
from PySide6.QtGui import QPainter, QColor, QPen, QPalette

from engine.actions import WaitAction
from gui.dialogs.preferences_dialog import PreferencesDialog
from gui.widgets.macro_item import get_dragged_item
from gui.widgets.macro_model import MacroRow, group_actions, ungroup_rows


class MacroListModel(QAbstractListModel):
    ActionRole = Qt.ItemDataRole.UserRole + 1  # returns the MacroRow

    def __init__(self, rows=None, parent=None):
        super().__init__(parent)
        self._rows = list(rows) if rows else []

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._rows)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return row.label()
        if role == MacroListModel.ActionRole:
            return row
        return None

    def flags(self, index):
        base = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if index.isValid():
            # Deliberately no ItemIsDropEnabled on real rows: if a row could
            # accept an "on item" drop, hovering dead-center over it is
            # ambiguous (insert before or after?) and Qt just no-ops. Without
            # the flag, Qt's own drop-indicator logic falls back to whichever
            # of above/below is closer to the cursor, which is what we want.
            return base | Qt.ItemFlag.ItemIsDragEnabled
        return base | Qt.ItemFlag.ItemIsDropEnabled  # empty-viewport area: allow append

    def supportedDropActions(self):
        return Qt.DropAction.MoveAction

    def mimeTypes(self):
        return ["application/x-macro-row-index", "text/plain"]

    def mimeData(self, indexes):
        mime = QMimeData()
        if indexes:
            mime.setData("application/x-macro-row-index", str(indexes[0].row()).encode())
            mime.setText("macro_item")
        return mime

    def dropMimeData(self, data, action, row, column, parent):
        if row == -1:
            row = self.rowCount()

        if data.hasFormat("application/x-macro-row-index"):
            # Qt-native internal reorder within this same view/model.
            src = int(bytes(data.data("application/x-macro-row-index")).decode())
            if src == row or src == row - 1:
                return False
            self.beginResetModel()
            moved = self._rows.pop(src)
            self._rows.insert(row - 1 if src < row else row, moved)
            self.endResetModel()
            return True

        if data.hasText() and data.text() == "macro_item":
            # Drag-in from ActionsPanel's existing template convention.
            dragged = get_dragged_item()
            if dragged is None or not dragged.is_template:
                return False
            new_action = copy.deepcopy(dragged.action)
            if isinstance(new_action, WaitAction):
                # The template itself carries a fixed placeholder duration;
                # use the user's configured default instead so they don't
                # have to open the options panel and retype it every time.
                new_action.seconds = PreferencesDialog.default_wait_seconds()
            self.beginInsertRows(QModelIndex(), row, row)
            self._rows.insert(row, MacroRow([new_action], configured=False))
            self.endInsertRows()
            return True

        return False

    def removeRows(self, row, count, parent=QModelIndex()):
        # Required for dragging a row out to another widget (e.g. dropping
        # it on ActionsPanel to delete it): after a cross-widget drop is
        # accepted as a MoveAction, Qt's own drag machinery calls this on
        # the *source* model to remove the dragged row. QAbstractListModel's
        # default implementation is a no-op, so without this override the
        # drop looks like it succeeds on the target side but the row never
        # actually leaves this list.
        if parent.isValid() or row < 0 or count <= 0 or row + count > len(self._rows):
            return False
        self.beginRemoveRows(QModelIndex(), row, row + count - 1)
        del self._rows[row:row + count]
        self.endRemoveRows()
        return True

    # --- helpers used by MacroPanel, not part of QAbstractItemModel API ---

    def set_rows(self, rows):
        self.beginResetModel()
        self._rows = list(rows)
        self.endResetModel()

    def row_at(self, i):
        return self._rows[i]

    def row_index_of(self, row):
        for i, r in enumerate(self._rows):
            if r is row:
                return i
        return None

    def remove_row(self, i):
        self.beginRemoveRows(QModelIndex(), i, i)
        del self._rows[i]
        self.endRemoveRows()

    def replace_row(self, i, new_row):
        self._rows[i] = new_row
        idx = self.index(i)
        self.dataChanged.emit(idx, idx)

    def replace_group_with_rows(self, i, new_rows):
        self.beginRemoveRows(QModelIndex(), i, i)
        del self._rows[i]
        self.endRemoveRows()
        if new_rows:
            self.beginInsertRows(QModelIndex(), i, i + len(new_rows) - 1)
            self._rows[i:i] = new_rows
            self.endInsertRows()


class MacroItemDelegate(QStyledItemDelegate):
    """Paints each row as its own rounded card so rows read as distinct
    items in the list rather than plain lines of text."""

    _ROW_HEIGHT = 32
    _WAIT_ROW_HEIGHT = 13  # waits carry no parameters worth much space, and recordings can have many of them
    _RADIUS = 6

    @staticmethod
    def _is_wait_row(row) -> bool:
        return row is not None and not row.is_group() and isinstance(row.actions[0], WaitAction)

    def paint(self, painter, option, index):
        row = index.data(MacroListModel.ActionRole)
        is_wait = self._is_wait_row(row)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)

        # Measured the ActionsPanel's actual rendered template cards directly
        # (grabbed a screenshot and sampled pixels) rather than assume: they
        # render as a filled rounded rect using the palette's Base role
        # (#2d2d2d here), with no visible border stroke -- not Window and
        # not Button as originally guessed. Match that exactly.
        palette = option.palette
        no_border = QPen(Qt.PenStyle.NoPen)
        if selected:
            bg = palette.color(QPalette.ColorRole.Highlight)
            border_pen = no_border
            text_color = palette.color(QPalette.ColorRole.HighlightedText)
        elif hovered:
            bg = palette.color(QPalette.ColorRole.Base).lighter(130)
            border_pen = no_border
            text_color = palette.color(QPalette.ColorRole.WindowText)
        else:
            bg = palette.color(QPalette.ColorRole.Base)
            border_pen = no_border
            text_color = palette.color(QPalette.ColorRole.WindowText)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = option.rect.adjusted(1, 1, -1, -1)
        radius = self._RADIUS * 0.5 if is_wait else self._RADIUS
        painter.setPen(border_pen)
        painter.setBrush(bg)
        painter.drawRoundedRect(rect, radius, radius)

        if is_wait:
            font = painter.font()
            font.setPointSizeF(max(6.0, font.pointSizeF() * 0.75))
            painter.setFont(font)

        painter.setPen(text_color)
        text_rect = rect.adjusted(8 if is_wait else 10, 0, -22, 0)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                          row.label() if row is not None else "")

        if row is not None and not row.is_configured():
            d = 8
            dot_rect = QRect(rect.right() - d - 8, rect.center().y() - d // 2, d, d)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#f5c400"))
            painter.drawEllipse(dot_rect)

        painter.restore()

    def sizeHint(self, option, index):
        row = index.data(MacroListModel.ActionRole)
        height = self._WAIT_ROW_HEIGHT if self._is_wait_row(row) else self._ROW_HEIGHT
        return QSize(option.rect.width(), height)


class MacroPanel(QWidget):
    selection_changed = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 10, 0, 0)
        outer_layout.setSpacing(0)

        label = QLabel("Macro")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)

        self._model = MacroListModel()
        self._view = QListView()
        self._view.setModel(self._model)
        self._view.setDragEnabled(True)
        self._view.setAcceptDrops(True)
        self._view.setDropIndicatorShown(True)
        self._view.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self._view.setDefaultDropAction(Qt.DropAction.MoveAction)
        self._view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._view.setItemDelegate(MacroItemDelegate(self._view))
        self._view.setMouseTracking(True)   # so the delegate's hover highlight updates live
        self._view.setSpacing(1)            # gap between rows so cards read as separate items (halved from 3)
        self._view.setFrameShape(QFrame.Shape.NoFrame)
        # QListView's viewport defaults to the Base palette role, but
        # ActionsPanel's plain QWidget panel uses Window -- match that so
        # the two columns share the same background instead of looking like
        # two different panels.
        self._view.viewport().setBackgroundRole(QPalette.ColorRole.Window)
        self._view.selectionModel().currentChanged.connect(self._on_current_changed)

        outer_layout.addWidget(label)
        outer_layout.addWidget(line)
        outer_layout.addWidget(self._view, 1)
        self.setFixedWidth(200)

    def _on_current_changed(self, current, previous):
        if not current.isValid():
            self.selection_changed.emit(None)
            return
        self.selection_changed.emit(self._model.row_at(current.row()))

    def load_actions(self, actions: list):
        """Replace the current macro with a list of action objects from a recording."""
        threshold = PreferencesDialog.move_merge_wait_threshold()
        self._model.set_rows(group_actions(actions, merge_wait_threshold=threshold))

    def get_actions(self):
        rows = [self._model.row_at(i) for i in range(self._model.rowCount())]
        return ungroup_rows(rows)

    def on_row_changed(self, row):
        """Connected to OptionsPanel.row_changed -- repaints the row after an edit."""
        i = self._model.row_index_of(row)
        if i is not None:
            self._model.replace_row(i, row)

    def expand_row(self, row):
        """Connected to OptionsPanel.expand_requested -- splits a collapsed
        move-group row into its individual MoveCursorAction rows."""
        i = self._model.row_index_of(row)
        if i is None or not row.is_group():
            return
        expanded = [MacroRow([a], configured=True) for a in row.actions]
        self._model.replace_group_with_rows(i, expanded)
        # The old group row object is gone; clear selection rather than let
        # the options panel keep showing a summary for a row that no longer
        # exists (Qt won't refire currentChanged since the index itself
        # didn't move, only what's at it).
        self._view.clearSelection()
        self._view.setCurrentIndex(QModelIndex())
        self.selection_changed.emit(None)

    def redraw_group(self, row, new_actions):
        """Connected to OptionsPanel.path_redrawn -- replaces a move group's
        internal actions with a freshly drawn path. A pause mid-drag becomes
        a WaitAction (see build_move_path), so the new actions aren't
        necessarily one homogeneous MoveCursorAction run any more -- re-run
        them through group_actions() so a paused drag correctly becomes
        multiple rows (Move/Wait/Move/...) instead of one MacroRow with
        mixed action types, which the group summary UI can't handle."""
        i = self._model.row_index_of(row)
        if i is None:
            return
        threshold = PreferencesDialog.move_merge_wait_threshold()
        new_rows = group_actions(new_actions, merge_wait_threshold=threshold)
        self._model.replace_group_with_rows(i, new_rows)
        # Old row object is gone; refresh the options panel to whatever's
        # now at that position (Qt won't refire currentChanged on its own
        # since the index itself didn't move, only what's at it).
        self.selection_changed.emit(new_rows[0] if new_rows else None)
