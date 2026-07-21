from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QLabel, QVBoxLayout,
)


class TitrationCalculationDialog(QDialog):
    """Local numeric fallback for calculation tasks; no speech/API required."""

    def __init__(self, task, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Titration calculation")
        self.setModal(True)
        self.setMinimumWidth(420)

        initial = task.get("initial_reading_ml", 4.6)
        final = task.get("final_reading_ml", 23.0)
        self.initial = self._spin(initial)
        self.final = self._spin(final)

        form = QFormLayout()
        form.addRow("Initial burette reading (mL)", self.initial)
        form.addRow("Final burette reading (mL)", self.final)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Submit
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        label = QLabel(task.get("prompt", "Calculate the titre value."))
        label.setWordWrap(True)
        layout.addWidget(label)
        layout.addLayout(form)
        layout.addWidget(buttons)

    @staticmethod
    def _spin(value):
        spin = QDoubleSpinBox()
        spin.setRange(0.0, 100.0)
        spin.setDecimals(2)
        spin.setSuffix(" mL")
        spin.setValue(float(value))
        return spin

    def calculated_value(self):
        return self.final.value() - self.initial.value()
