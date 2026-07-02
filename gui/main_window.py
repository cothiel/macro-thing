from PySide6.QtCore import QSize, Signal, QObject, QSettings
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

from pynput import keyboard as _kb

from gui.dialogs.preferences_dialog import PreferencesDialog
from gui.dialogs.hotkeys_dialog import HotkeysDialog, pynput_to_display
from engine.precision_translator import translate_precision
from gui.widgets.actions_panel import ActionsPanel
from gui.widgets.macro_panel import MacroPanel
from gui.widgets.options_panel import OptionsPanel
from engine.player import MacroPlayer
from engine.recorder import MacroRecorder

# Need this so when the player thread is finished, it can signal the play button to uncheck
class _PlayerBridge(QObject):
    finished = Signal()
    hotkey_triggered = Signal()

# same thing as _PlayerBridge, but for the recorder.
class _RecorderBridge(QObject):
    finished = Signal()
    hotkey_triggered = Signal()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Macro (WIP)")
        self._player = None
        self._player_bridge = _PlayerBridge()
        self._recorder_bridge = _RecorderBridge()

        self._build_toolbar()
        self._build_editor_panel()
        self._connect_signals()

        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(self.toolbar_widget, 0)
        main_layout.addWidget(self.editor_panel, 1)
        self.setCentralWidget(container)
        self.setFixedSize(400, self.toolbar_widget.sizeHint().height())

        self._start_global_hotkeys()



        

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
        self.hotkeys_action = settings_menu.addAction("Hotkeys...")
        self.hotkeys_action.triggered.connect(self._open_hotkeys)
        self.preferences_action = settings_menu.addAction("Preferences...")
        self.preferences_action.triggered.connect(self._open_preferences)
        self.settings_btn.setMenu(settings_menu)
        self.settings_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.settings_btn)

        toolbar_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        toolbar_widget.setFixedHeight(40)
        self.toolbar_widget = toolbar_widget

    def _build_editor_panel(self):
        self.actions_panel = ActionsPanel()
        self.macro_panel = MacroPanel()
        self.options_panel = OptionsPanel()

        self.editor_panel = QWidget()
        layout = QHBoxLayout(self.editor_panel)
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
        self.editor_panel.setVisible(False)

    def _connect_signals(self):
        self.editor_action.toggled.connect(self.on_editor_toggled)
        self.play_action.toggled.connect(self.on_play_toggled)
        self._player_bridge.finished.connect(self._on_playback_complete)
        self.record_action.toggled.connect(self.on_record_toggled)
        #self._recorder_bridge.finished.connect(self._on_record_complete) # idk if I actually need this, recorder won't finish on its own, it can only be toggled off and on
        self.macro_panel.selection_changed.connect(self.options_panel.show_for)
        self.options_panel.row_changed.connect(self.macro_panel.on_row_changed)
        self.options_panel.expand_requested.connect(self.macro_panel.expand_row)
        self.options_panel.path_redrawn.connect(self.macro_panel.redraw_group)
        self._recorder_bridge.hotkey_triggered.connect(self._on_record_hotkey)
        self._player_bridge.hotkey_triggered.connect(self._on_play_hotkey)
    
    def open_btn_clicked(self, s):
        print("Open Button Clicked")
    
    def on_editor_toggled(self, checked: bool):
        if checked:
            self.editor_panel.setVisible(True)
            self.setFixedSize(550, 500)
        else:
            self.editor_panel.setVisible(False)
            self.setFixedSize(400, 40)

    def on_play_toggled(self, checked):
        if checked:
            actions = self.macro_panel.get_actions()
            self._player = MacroPlayer(
                actions,
                on_complete=self._player_bridge.finished.emit,
                repeat_count=PreferencesDialog.repeat_count(),
                continuous=PreferencesDialog.continuous_playback_enabled(),
            )
            self._player.start()
        else:
            if self._player:
                self._player.stop()

    def on_record_toggled(self, checked):
        if checked:
            self._recorder = MacroRecorder()
            self._recorder.start()
        else:
            self._recorder.stop()
            if PreferencesDialog.precision_recorder_enabled():
                events = self._recorder.get_events()
                actions = translate_precision(events)
                self.macro_panel.load_actions(actions)

    def _on_record_hotkey(self):
        self.record_action.setChecked(not self.record_action.isChecked())

    def _on_play_hotkey(self):
        self.play_action.setChecked(not self.play_action.isChecked())

    def _start_global_hotkeys(self):
        settings = QSettings("tinytask", "tinytask")
        record_key = str(settings.value("hotkeys/record", "<f9>"))
        play_key = str(settings.value("hotkeys/playback", "<f10>"))

        self._global_hotkeys = _kb.GlobalHotKeys({
            record_key: self._recorder_bridge.hotkey_triggered.emit,
            play_key: self._player_bridge.hotkey_triggered.emit,
        })
        self._global_hotkeys.start()

        self.record_action.setToolTip(f"Record  [{pynput_to_display(record_key)}]")
        self.play_action.setToolTip(f"Play  [{pynput_to_display(play_key)}]")

    def _open_hotkeys(self):
        self._global_hotkeys.stop()
        self._global_hotkeys.join()
        dlg = HotkeysDialog(self)
        dlg.exec()
        self._start_global_hotkeys()

    def closeEvent(self, event):
        self._global_hotkeys.stop()
        self._global_hotkeys.join()
        super().closeEvent(event)

    def _open_preferences(self):
        PreferencesDialog(self).exec()

    def _on_playback_complete(self):
        self.play_action.setChecked(False)


