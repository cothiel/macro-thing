from PySide6.QtCore import QSettings
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QGroupBox,
    QCheckBox,
    QDialogButtonBox,
)


class PreferencesDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.setMinimumWidth(300)

        self._settings = QSettings("tinytask", "tinytask")

        layout = QVBoxLayout(self)

        recording_group = QGroupBox("Recording")
        group_layout = QVBoxLayout(recording_group)

        self.precision_recorder_cb = QCheckBox("Precision recorder")
        self.precision_recorder_cb.setToolTip(
            "Translate every recorded pynput action into a pyautogui-compatible action."
        )
        self.precision_recorder_cb.setChecked(
            self._settings.value("recording/precision_recorder", False, type=bool)
        )
        group_layout.addWidget(self.precision_recorder_cb)
        layout.addWidget(recording_group)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._save_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _save_and_accept(self):
        self._settings.setValue("recording/precision_recorder", self.precision_recorder_cb.isChecked())
        self.accept()

    @staticmethod
    def precision_recorder_enabled() -> bool:
        return QSettings("tinytask", "tinytask").value("recording/precision_recorder", False, type=bool)
