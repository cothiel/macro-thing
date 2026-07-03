from PySide6.QtCore import QSettings
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QGroupBox,
    QCheckBox,
    QSpinBox,
    QDoubleSpinBox,
    QDialogButtonBox,
)


class PreferencesDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.setMinimumWidth(300)

        self._settings = QSettings("Macro", "Macro")

        layout = QVBoxLayout(self)

        playback_group = QGroupBox("Playback")
        playback_layout = QFormLayout(playback_group)

        self.repeat_count_spin = QSpinBox()
        self.repeat_count_spin.setRange(1, 9999)
        self.repeat_count_spin.setValue(
            self._settings.value("playback/repeat_count", 1, type=int)
        )
        playback_layout.addRow("Repeat count:", self.repeat_count_spin)

        self.continuous_cb = QCheckBox("Continuous playback (loop until stopped)")
        self.continuous_cb.setChecked(
            self._settings.value("playback/continuous", False, type=bool)
        )
        self.continuous_cb.toggled.connect(self.repeat_count_spin.setDisabled)
        self.repeat_count_spin.setDisabled(self.continuous_cb.isChecked())
        playback_layout.addRow(self.continuous_cb)

        layout.addWidget(playback_group)

        editor_group = QGroupBox("Editor")
        editor_layout = QFormLayout(editor_group)

        self.default_wait_spin = QDoubleSpinBox()
        self.default_wait_spin.setRange(0.01, 3600.0)
        self.default_wait_spin.setDecimals(2)
        self.default_wait_spin.setSingleStep(0.1)
        self.default_wait_spin.setSuffix(" s")
        self.default_wait_spin.setToolTip(
            "Starting duration for a new Wait action dragged in from the Actions panel."
        )
        self.default_wait_spin.setValue(
            self._settings.value("editor/default_wait_seconds", 1.0, type=float)
        )
        editor_layout.addRow("Default wait duration:", self.default_wait_spin)

        self.merge_wait_spin = QDoubleSpinBox()
        self.merge_wait_spin.setRange(0.0, 5.0)
        self.merge_wait_spin.setDecimals(2)
        self.merge_wait_spin.setSingleStep(0.05)
        self.merge_wait_spin.setSuffix(" s")
        self.merge_wait_spin.setToolTip(
            "A Wait shorter than this, sandwiched between two move bursts, is shown as "
            "part of the same Move row instead of splitting it into separate rows. "
            "Set to 0 to never merge -- every wait always gets its own row."
        )
        self.merge_wait_spin.setValue(
            self._settings.value("editor/move_merge_wait_threshold", 0.3, type=float)
        )
        editor_layout.addRow("Merge short waits under:", self.merge_wait_spin)

        layout.addWidget(editor_group)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._save_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _save_and_accept(self):
        self._settings.setValue("playback/repeat_count", self.repeat_count_spin.value())
        self._settings.setValue("playback/continuous", self.continuous_cb.isChecked())
        self._settings.setValue("editor/default_wait_seconds", self.default_wait_spin.value())
        self._settings.setValue("editor/move_merge_wait_threshold", self.merge_wait_spin.value())
        self.accept()

    @staticmethod
    def repeat_count() -> int:
        return QSettings("Macro", "Macro").value("playback/repeat_count", 1, type=int)

    @staticmethod
    def continuous_playback_enabled() -> bool:
        return QSettings("Macro", "Macro").value("playback/continuous", False, type=bool)

    @staticmethod
    def default_wait_seconds() -> float:
        return QSettings("Macro", "Macro").value("editor/default_wait_seconds", 1.0, type=float)

    @staticmethod
    def move_merge_wait_threshold() -> float:
        return QSettings("Macro", "Macro").value("editor/move_merge_wait_threshold", 0.3, type=float)
