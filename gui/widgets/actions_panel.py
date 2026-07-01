import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QFrame, QScrollArea
)
from PySide6.QtCore import Qt

from engine.actions import (
    ClickAction, RepeatClickAction, MoveCursorAction, ClickDragAction,
    WaitAction, PressKeyAction, HotkeyAction, TypeTextAction, HoldKeyAction,
)
from gui.widgets.macro_item import MacroItem, get_dragged_item


_TEMPLATES = [
    ClickAction(0, 0),
    RepeatClickAction(0, 0, 1),
    MoveCursorAction(0, 0),
    ClickDragAction(0, 0),
    WaitAction(1),
    PressKeyAction('a'),
    HotkeyAction(['ctrl', 'c']),
    TypeTextAction(''),
    HoldKeyAction('a', 1),
]


class _DropZone(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        for action in _TEMPLATES:
            layout.addWidget(MacroItem(action, is_template=True))

    def dragEnterEvent(self, event):
        if event.mimeData().hasText() and event.mimeData().text() == "macro_item":
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        item = get_dragged_item()
        if item is not None:
            # Legacy path: dragged-from widget is still a real MacroItem.
            if item.is_template:
                event.ignore()
                return
            item.setParent(None)
            item.deleteLater()
            event.acceptProposedAction()
            return

        # Dragged from MacroPanel's QListView -- no MacroItem widget exists
        # for a real macro row anymore. Accepting a MoveAction here makes
        # Qt remove the row from the source model automatically.
        if event.mimeData().hasFormat("application/x-macro-row-index"):
            event.setDropAction(Qt.DropAction.MoveAction)
            event.acceptProposedAction()
            return

        event.ignore()


class ActionsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 10, 0, 0)
        outer_layout.setSpacing(0)

        label = QLabel("Actions")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(_DropZone())

        outer_layout.addWidget(label)
        outer_layout.addWidget(line)
        outer_layout.addWidget(scroll, 1)
        self.setFixedWidth(150)
