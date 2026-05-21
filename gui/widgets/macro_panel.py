import sys
import os
import copy

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QFrame, QScrollArea
)
from PySide6.QtCore import Qt, Signal

from gui.widgets.macro_item import MacroItem, get_dragged_item


class _DropZone(QWidget):
    def __init__(self, on_item_click, parent=None):
        super().__init__(parent)
        self._on_item_click = on_item_click
        self.setAcceptDrops(True)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(4, 4, 4, 4)
        self._layout.setSpacing(4)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._indicator = QFrame(self)
        self._indicator.setFixedHeight(3)
        self._indicator.setStyleSheet("background-color: #0078d4;")
        self._indicator.setVisible(False)
        self._target_real_idx = -1

    def _connect_item(self, item: MacroItem):
        item.item_selected.connect(self._on_item_click)

    def _real_items(self):
        result = []
        for i in range(self._layout.count()):
            item = self._layout.itemAt(i)
            if item is None:
                continue
            w = item.widget()
            if w is not None and w is not self._indicator:
                result.append(w)
        return result

    def _update_indicator(self, pos):
        dragged = get_dragged_item()
        real_excl_dragged = [w for w in self._real_items() if w is not dragged]

        target_real_idx = len(real_excl_dragged)
        for i, w in enumerate(real_excl_dragged):
            mid = w.geometry().top() + w.geometry().height() // 2
            if pos.y() < mid:
                target_real_idx = i
                break

        if target_real_idx == self._target_real_idx:
            return

        self._target_real_idx = target_real_idx
        self._layout.removeWidget(self._indicator)

        if target_real_idx < len(real_excl_dragged):
            insert_at = self._layout.indexOf(real_excl_dragged[target_real_idx])
        else:
            insert_at = self._layout.count()

        self._layout.insertWidget(insert_at, self._indicator)
        self._indicator.setVisible(True)

    def _hide_indicator(self):
        self._layout.removeWidget(self._indicator)
        self._indicator.setVisible(False)
        self._target_real_idx = -1

    def dragEnterEvent(self, event):
        if event.mimeData().hasText() and event.mimeData().text() == "macro_item":
            self._update_indicator(event.position().toPoint())
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        self._update_indicator(event.position().toPoint())
        event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self._hide_indicator()
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        item = get_dragged_item()
        if item is None:
            self._hide_indicator()
            event.ignore()
            return

        indicator_layout_idx = self._layout.indexOf(self._indicator)
        self._hide_indicator()

        if item.is_template:
            new_item = MacroItem(copy.deepcopy(item.action))
            self._connect_item(new_item)
            self._layout.insertWidget(indicator_layout_idx, new_item)
        else:
            item_layout_idx = self._layout.indexOf(item)
            self._layout.removeWidget(item)
            final_idx = indicator_layout_idx - 1 if item_layout_idx < indicator_layout_idx else indicator_layout_idx
            self._layout.insertWidget(final_idx, item)

        event.acceptProposedAction()


class MacroPanel(QWidget):
    selection_changed = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._selected_item = None

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 10, 0, 0)
        outer_layout.setSpacing(0)

        label = QLabel("Macro")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._drop_zone = _DropZone(on_item_click=self._on_item_clicked)
        scroll.setWidget(self._drop_zone)

        outer_layout.addWidget(label)
        outer_layout.addWidget(line)
        outer_layout.addWidget(scroll, 1)
        self.setFixedWidth(200)

    def _on_item_clicked(self, item: MacroItem):
        if self._selected_item is item:
            self._deselect_current()
            self.selection_changed.emit(None)
            return
        self._deselect_current()
        self._selected_item = item
        item.set_selected(True)
        item.destroyed.connect(self._on_selected_destroyed)
        self.selection_changed.emit(item)

    def _deselect_current(self):
        if self._selected_item is not None:
            try:
                self._selected_item.destroyed.disconnect(self._on_selected_destroyed)
                self._selected_item.set_selected(False)
            except RuntimeError:
                pass
            self._selected_item = None

    def _on_selected_destroyed(self):
        self._selected_item = None
        self.selection_changed.emit(None)

    def get_actions(self):
        layout = self._drop_zone._layout
        actions = []
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if item is None:
                continue
            widget = item.widget()
            if isinstance(widget, MacroItem):
                actions.append(widget.action)
        return actions
