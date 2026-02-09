from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QPushButton, QFormLayout, QWidget, QStackedWidget,
    QMessageBox, QFileDialog, QCheckBox, QScrollArea, QGridLayout,
    QGroupBox, QTabWidget
)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QKeySequence, QPixmap, QFont, QIcon

import os

# Curated emoji database grouped by category
EMOJI_DATABASE = {
    "Common": [
        "\u2699\ufe0f", "\u2b50", "\u2764\ufe0f", "\u2714\ufe0f", "\u274c", "\u26a0\ufe0f",
        "\u2709\ufe0f", "\u270f\ufe0f", "\u2702\ufe0f", "\u267b\ufe0f",
        "\U0001f4c1", "\U0001f4c2", "\U0001f4c4", "\U0001f4cb", "\U0001f4ce",
        "\U0001f50d", "\U0001f512", "\U0001f513", "\U0001f511", "\U0001f6e0\ufe0f",
    ],
    "Apps & Tools": [
        "\U0001f4bb", "\U0001f5a5\ufe0f", "\u2328\ufe0f", "\U0001f5b1\ufe0f", "\U0001f5a8\ufe0f",
        "\U0001f4f7", "\U0001f3a5", "\U0001f3b5", "\U0001f3ae", "\U0001f4e7",
        "\U0001f310", "\U0001f4e1", "\U0001f4be", "\U0001f4bf", "\U0001f4c0",
        "\U0001f4f1", "\U0001f4de", "\U0001f4e2", "\U0001f50a", "\U0001f507",
    ],
    "Actions": [
        "\u25b6\ufe0f", "\u23f8\ufe0f", "\u23f9\ufe0f", "\u23ed\ufe0f", "\u23ee\ufe0f",
        "\U0001f504", "\u2795", "\u2796", "\u2716\ufe0f", "\u2611\ufe0f",
        "\U0001f4e5", "\U0001f4e4", "\U0001f501", "\U0001f500", "\U0001f502",
        "\U0001f519", "\U0001f51a", "\U0001f51b", "\U0001f51c", "\U0001f51d",
    ],
    "Symbols": [
        "\U0001f534", "\U0001f7e0", "\U0001f7e1", "\U0001f7e2", "\U0001f535", "\U0001f7e3",
        "\u26aa", "\u26ab", "\U0001f7e4", "\u2b1c",
        "\u2b06\ufe0f", "\u2b07\ufe0f", "\u27a1\ufe0f", "\u2b05\ufe0f",
        "\U0001f197", "\U0001f195", "\U0001f198", "\U0001f199", "\u2139\ufe0f", "\u203c\ufe0f",
    ],
    "Faces & People": [
        "\U0001f600", "\U0001f60e", "\U0001f914", "\U0001f4aa", "\U0001f44d",
        "\U0001f44e", "\U0001f44b", "\u270c\ufe0f", "\U0001f596", "\U0001f91d",
    ],
    "Nature & Weather": [
        "\u2600\ufe0f", "\U0001f319", "\u2b50", "\u26a1", "\U0001f525",
        "\U0001f4a7", "\u2744\ufe0f", "\U0001f308", "\U0001f331", "\U0001f3b2",
    ],
}


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


class EmojiPickerDialog(QDialog):
    """A dialog showing categorized emoji for selection."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Emoji")
        self.setMinimumSize(420, 350)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.selected_emoji = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        tabs = QTabWidget()
        for category, emojis in EMOJI_DATABASE.items():
            page = QWidget()
            grid = QGridLayout(page)
            grid.setSpacing(4)
            cols = 10
            for i, emoji in enumerate(emojis):
                btn = QPushButton(emoji)
                btn.setFixedSize(36, 36)
                btn.setFont(QFont("Sans", 16))
                btn.setStyleSheet("QPushButton { border: 1px solid #555; border-radius: 4px; }"
                                  "QPushButton:hover { background: #4a6fa5; }")
                btn.clicked.connect(lambda checked, e=emoji: self._select(e))
                grid.addWidget(btn, i // cols, i % cols)
            grid.setRowStretch(i // cols + 1, 1)
            tabs.addTab(page, category)

        layout.addWidget(tabs)

        # Custom emoji input
        custom_layout = QHBoxLayout()
        custom_layout.addWidget(QLabel("Or type/paste:"))
        self._custom_edit = QLineEdit()
        self._custom_edit.setPlaceholderText("Paste any emoji here...")
        self._custom_edit.setMaxLength(4)
        custom_layout.addWidget(self._custom_edit)
        use_btn = QPushButton("Use")
        use_btn.clicked.connect(self._use_custom)
        custom_layout.addWidget(use_btn)
        layout.addLayout(custom_layout)

    def _select(self, emoji):
        self.selected_emoji = emoji
        self.accept()

    def _use_custom(self):
        text = self._custom_edit.text().strip()
        if text:
            self.selected_emoji = text
            self.accept()


class ActionDialog(QDialog):
    """Dialog to configure an action for a wheel slot."""

    def __init__(self, slot_data=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configure Action")
        self.setMinimumWidth(440)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.result_data = None
        self._icon_value = None
        self._icon_type = None  # "emoji" or "image"
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

        # ── Icon section ──────────────────────────────────────────
        icon_group = QGroupBox("Icon (optional)")
        icon_layout = QHBoxLayout(icon_group)

        self._icon_preview = QLabel()
        self._icon_preview.setFixedSize(40, 40)
        self._icon_preview.setAlignment(Qt.AlignCenter)
        self._icon_preview.setStyleSheet(
            "border: 1px solid #666; border-radius: 4px; background: #2a2a2a;"
        )
        self._icon_preview.setFont(QFont("Sans", 20))
        icon_layout.addWidget(self._icon_preview)

        icon_btn_layout = QVBoxLayout()

        emoji_btn = QPushButton("Choose Emoji...")
        emoji_btn.clicked.connect(self._pick_emoji)
        icon_btn_layout.addWidget(emoji_btn)

        image_btn = QPushButton("Upload Image...")
        image_btn.clicked.connect(self._pick_image)
        icon_btn_layout.addWidget(image_btn)

        icon_layout.addLayout(icon_btn_layout)

        clear_icon_btn = QPushButton("Clear")
        clear_icon_btn.setFixedWidth(60)
        clear_icon_btn.clicked.connect(self._clear_icon)
        icon_layout.addWidget(clear_icon_btn)

        icon_layout.addStretch()

        self._show_label_cb = QCheckBox("Show label")
        self._show_label_cb.setChecked(True)
        icon_layout.addWidget(self._show_label_cb)

        layout.addWidget(icon_group)

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

        # Restore icon state
        icon = data.get("icon")
        icon_type = data.get("icon_type")
        if icon and icon_type:
            self._icon_value = icon
            self._icon_type = icon_type
            self._update_icon_preview()

        show_label = data.get("show_label", True)
        self._show_label_cb.setChecked(show_label)

    def _on_type_changed(self, index):
        self._stack.setCurrentIndex(index)

    def _browse_program(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Program", "/usr/bin"
        )
        if path:
            self._program_edit.setText(path)

    # ── Icon methods ──────────────────────────────────────────────

    def _pick_emoji(self):
        dlg = EmojiPickerDialog(self)
        if dlg.exec_() and dlg.selected_emoji:
            self._icon_value = dlg.selected_emoji
            self._icon_type = "emoji"
            self._update_icon_preview()

    def _pick_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Icon Image", "",
            "Images (*.png *.jpg *.jpeg *.svg *.bmp *.ico)"
        )
        if path:
            # Copy image to icons directory next to config
            icons_dir = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "icons"
            )
            os.makedirs(icons_dir, exist_ok=True)
            dest = os.path.join(icons_dir, os.path.basename(path))
            if os.path.abspath(path) != os.path.abspath(dest):
                import shutil
                shutil.copy2(path, dest)
            self._icon_value = dest
            self._icon_type = "image"
            self._update_icon_preview()

    def _clear_icon(self):
        self._icon_value = None
        self._icon_type = None
        self._icon_preview.clear()

    def _update_icon_preview(self):
        if self._icon_type == "emoji":
            self._icon_preview.setText(self._icon_value)
        elif self._icon_type == "image" and os.path.exists(self._icon_value):
            pixmap = QPixmap(self._icon_value).scaled(
                32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self._icon_preview.setPixmap(pixmap)

    # ── Dialog result ─────────────────────────────────────────────

    def _on_clear(self):
        self.result_data = {
            "label": "Select to add action", "type": None, "value": None,
            "icon": None, "icon_type": None, "show_label": True,
        }
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

        self.result_data = {
            "label": label,
            "type": action_type,
            "value": value,
            "icon": self._icon_value,
            "icon_type": self._icon_type,
            "show_label": self._show_label_cb.isChecked(),
        }
        self.accept()
