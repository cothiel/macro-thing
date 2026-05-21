from PySide6.QtCore import QSize, Signal, QObject
from PySide6.QtGui import QAction, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QToolButton,
    QMenu,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QSizePolicy,
    QFrame,
)
import qdarktheme
from gui.widgets.actions_panel import ActionsPanel
from gui.widgets.macro_panel import MacroPanel
from gui.widgets.options_panel import OptionsPanel
from engine.player import MacroPlayer

# Need this so when the player thread is finished, it can signal the play button to uncheck
class _PlayerBridge(QObject):
    finished = Signal()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Macro (WIP)")
        self._player = None
        self._bridge = _PlayerBridge()

        self._build_toolbar()
        self._build_advanced_panel()
        self._connect_signals()

        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(self.toolbar_widget, 0)
        main_layout.addWidget(self.advanced_panel, 1)
        self.setCentralWidget(container)
        self.setFixedSize(400, self.toolbar_widget.sizeHint().height())



        

    def _build_toolbar(self):
        toolbar_widget = QWidget()
        layout = QHBoxLayout(toolbar_widget)
        toolbar_widget.setStyleSheet("QToolButton {padding: 4px 10px;}")
        layout.setContentsMargins(3,3,3,3) # margin around toolbar elements
        layout.setSpacing(4) # Spacing between toolbar elements

        self.open_action = QAction("Open", self)

        self.save_action = QAction("Save", self)

        self.record_action = QAction("Record", self)
        self.record_action.setCheckable(True)

        self.play_action = QAction("Play", self)
        self.play_action.setCheckable(True)

        self.editor_action = QAction("Editor", self)
        self.editor_action.setCheckable(True)

        for action in [self.open_action, self.save_action, self.record_action,
                       self.play_action, self.editor_action]:
            btn = QToolButton()
            btn.setDefaultAction(action)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            layout.addWidget(btn)

        # This needs to open a menu so its a toolbutton.
        self.settings_btn = QToolButton(self)
        self.settings_btn.setText("Settings")
        self.settings_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        settings_menu = QMenu(self)
        settings_menu.addAction("Hotkeys...")
        settings_menu.addAction("Preferences...")
        self.settings_btn.setMenu(settings_menu)
        self.settings_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.settings_btn)

        toolbar_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        toolbar_widget.setFixedHeight(40)
        self.toolbar_widget = toolbar_widget

    def _build_advanced_panel(self):
        self.actions_panel = ActionsPanel()
        self.macro_panel = MacroPanel()
        self.options_panel = OptionsPanel()

        self.advanced_panel = QWidget()
        layout = QHBoxLayout(self.advanced_panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        line1 = QFrame()
        line1.setFrameShape(QFrame.Shape.VLine)
        line1.setFrameShadow(QFrame.Shadow.Sunken)
        line2 = QFrame()
        line2.setFrameShape(QFrame.Shape.VLine)
        line2.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(self.actions_panel)
        layout.addWidget(line1)
        layout.addWidget(self.macro_panel)
        layout.addWidget(line2)
        layout.addWidget(self.options_panel)
        self.advanced_panel.setVisible(False)

    def _connect_signals(self):
        self.editor_action.toggled.connect(self.on_editor_toggled)
        self.play_action.toggled.connect(self.on_play_toggled)
        self._bridge.finished.connect(self._on_playback_complete)
        self.macro_panel.selection_changed.connect(self.options_panel.show_for)
    
    def open_btn_clicked(self, s):
        print("Open Button Clicked")
    
    def on_editor_toggled(self, checked: bool):
        if checked:
            self.advanced_panel.setVisible(True)
            self.setFixedSize(550, 500)
        else:
            self.advanced_panel.setVisible(False)
            self.setFixedSize(400, 40)

    def on_play_toggled(self, checked):
        if checked:
            actions = self.macro_panel.get_actions()
            self._player = MacroPlayer(actions, on_complete=self._bridge.finished.emit)
            self._player.start()
        else:
            if self._player:
                self._player.stop()

    def _on_playback_complete(self):
        self.play_action.setChecked(False)


