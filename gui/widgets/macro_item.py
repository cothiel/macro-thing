import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QApplication
from PySide6.QtCore import Qt, QMimeData, QPoint, Signal
from PySide6.QtGui import QDrag, QPainter, QPen, QColor
from engine.actions import BaseAction

_dragged_item: 'MacroItem | None' = None


def get_dragged_item() -> 'MacroItem | None':
    return _dragged_item


class MacroItem(QFrame):
    item_selected = Signal(object)

    def __init__(self, action: BaseAction, is_template: bool = False, parent=None):
        super().__init__(parent)
        self.action = action
        self.is_template = is_template
        self._drag_start = QPoint()
        self._selected = False
        self._configured = is_template  # templates don't need the indicator
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)
        self._label = QLabel(self._display_text())
        self._label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(self._label)

        self._indicator = QLabel()
        self._indicator.setFixedSize(10, 10)
        self._indicator.setStyleSheet(
            "background: #f5c400; border-radius: 5px; color:black"
        )

        self._indicator.setToolTip("Don't forget to set parameters!")
        self._indicator.setVisible(not self._configured)
        layout.addWidget(self._indicator)

    def _display_text(self) -> str:
        return self.action.to_dict().get("Type", "Action")

    def refresh(self):
        self._label.setText(self._display_text())

    def set_selected(self, selected: bool):
        self._selected = selected
        self.update()

    def mark_configured(self):
        if not self._configured:
            self._configured = True
            self._indicator.setVisible(False)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._selected:
            painter = QPainter(self)
            pen = QPen(QColor("#0078d4"))
            pen.setWidth(3)
            painter.setPen(pen)
            painter.drawRect(self.rect().adjusted(2, 2, -2, -2))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if (event.position().toPoint() - self._drag_start).manhattanLength() < QApplication.startDragDistance():
                self.item_selected.emit(self)
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            super().mouseMoveEvent(event)
            return
        if (event.position().toPoint() - self._drag_start).manhattanLength() < QApplication.startDragDistance():
            super().mouseMoveEvent(event)
            return
        self._start_drag()

    def _start_drag(self):
        global _dragged_item
        _dragged_item = self
        mime = QMimeData()
        mime.setText("macro_item")
        pixmap = self.grab()
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.setPixmap(pixmap)
        drag.setHotSpot(pixmap.rect().center())

        if not self.is_template:
            self.setVisible(False)

        drag.exec(Qt.DropAction.MoveAction)

        if not self.is_template and self.parent() is not None:
            self.setVisible(True)
        _dragged_item = None
