from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QPushButton, QFormLayout, QWidget, QStackedWidget,
    QMessageBox, QFileDialog
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeySequence


class KeySequenceEdit(QLineEdit):
    """A line edit that captures a key combination when focused."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setPlaceholderText("Click here, then press a key combo...")
        self._keys = []

    def keyPressEvent(self, event):
        modifiers = event.modifiers()
        key = event.key()

        if key in (Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta):
            return

        seq = QKeySequence(int(modifiers) | key)
        self.setText(seq.toString())

    def get_value(self):
        return self.text()


class ActionDialog(QDialog):
    """Dialog to configure an action for a wheel slot."""

    def __init__(self, slot_data=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configure Action")
        self.setMinimumWidth(400)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.result_data = None
        self._build_ui(slot_data)

    def _build_ui(self, slot_data):
        layout = QVBoxLayout(self)

        # Label
        label_layout = QFormLayout()
        self._label_edit = QLineEdit()
        self._label_edit.setPlaceholderText("Display name on the wheel")
        label_layout.addRow("Label:", self._label_edit)
        layout.addLayout(label_layout)

        # Action type selector
        type_layout = QFormLayout()
        self._type_combo = QComboBox()
        self._type_combo.addItems(["Keystroke", "Shell Command", "Launch Program", "Folder"])
        self._type_combo.currentIndexChanged.connect(self._on_type_changed)
        type_layout.addRow("Action Type:", self._type_combo)
        layout.addLayout(type_layout)

        # Stacked widget for type-specific inputs
        self._stack = QStackedWidget()

        # Page 0: Keystroke
        keystroke_page = QWidget()
        ks_layout = QVBoxLayout(keystroke_page)
        ks_layout.setContentsMargins(0, 0, 0, 0)
        self._key_edit = KeySequenceEdit()
        ks_layout.addWidget(QLabel("Press the key combination:"))
        ks_layout.addWidget(self._key_edit)
        self._stack.addWidget(keystroke_page)

        # Page 1: Shell Command
        cmd_page = QWidget()
        cmd_layout = QVBoxLayout(cmd_page)
        cmd_layout.setContentsMargins(0, 0, 0, 0)
        self._cmd_edit = QLineEdit()
        self._cmd_edit.setPlaceholderText("e.g., notify-send 'Hello!'")
        cmd_layout.addWidget(QLabel("Command to run:"))
        cmd_layout.addWidget(self._cmd_edit)
        self._stack.addWidget(cmd_page)

        # Page 2: Launch Program
        launch_page = QWidget()
        launch_layout = QVBoxLayout(launch_page)
        launch_layout.setContentsMargins(0, 0, 0, 0)
        self._program_edit = QLineEdit()
        self._program_edit.setPlaceholderText("e.g., /usr/bin/firefox")
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_program)
        prog_row = QHBoxLayout()
        prog_row.addWidget(self._program_edit)
        prog_row.addWidget(browse_btn)
        launch_layout.addWidget(QLabel("Program path:"))
        launch_layout.addLayout(prog_row)
        self._stack.addWidget(launch_page)

        # Page 3: Folder
        folder_page = QWidget()
        folder_layout = QVBoxLayout(folder_page)
        folder_layout.setContentsMargins(0, 0, 0, 0)
        self._folder_label = QLabel(
            "This will create a new sub-wheel with 8 more slots.\n"
            "The top-right slot will automatically be 'Back'."
        )
        folder_layout.addWidget(self._folder_label)
        self._stack.addWidget(folder_page)

        layout.addWidget(self._stack)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        clear_btn = QPushButton("Clear Action")
        clear_btn.clicked.connect(self._on_clear)
        btn_layout.addWidget(clear_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        ok_btn = QPushButton("OK")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self._on_ok)
        btn_layout.addWidget(ok_btn)

        layout.addLayout(btn_layout)

        # Pre-fill if editing existing slot
        if slot_data and slot_data.get("type"):
            self._prefill(slot_data)

    def _prefill(self, data):
        self._label_edit.setText(data.get("label", ""))
        type_map = {"keystroke": 0, "command": 1, "launch": 2, "folder": 3}
        idx = type_map.get(data.get("type"), 0)
        self._type_combo.setCurrentIndex(idx)
        self._stack.setCurrentIndex(idx)

        value = data.get("value", "")
        if idx == 0:
            self._key_edit.setText(value or "")
        elif idx == 1:
            self._cmd_edit.setText(value or "")
        elif idx == 2:
            self._program_edit.setText(value or "")

    def _on_type_changed(self, index):
        self._stack.setCurrentIndex(index)

    def _browse_program(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Program", "/usr/bin"
        )
        if path:
            self._program_edit.setText(path)

    def _on_clear(self):
        self.result_data = {"label": "Select to add action", "type": None, "value": None}
        self.accept()

    def _on_ok(self):
        label = self._label_edit.text().strip()
        idx = self._type_combo.currentIndex()

        type_names = ["keystroke", "command", "launch", "folder"]
        action_type = type_names[idx]

        if idx == 0:
            value = self._key_edit.get_value()
            if not value:
                QMessageBox.warning(self, "Missing", "Please press a key combination.")
                return
            if not label:
                label = value
        elif idx == 1:
            value = self._cmd_edit.text().strip()
            if not value:
                QMessageBox.warning(self, "Missing", "Please enter a command.")
                return
            if not label:
                label = value[:30]
        elif idx == 2:
            value = self._program_edit.text().strip()
            if not value:
                QMessageBox.warning(self, "Missing", "Please enter a program path.")
                return
            if not label:
                label = value.split("/")[-1]
        elif idx == 3:
            value = None
            if not label:
                label = "Folder"

        self.result_data = {"label": label, "type": action_type, "value": value}
        self.accept()
