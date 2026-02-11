from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox,
    QPushButton, QFormLayout, QGroupBox, QComboBox,
    QSlider, QCheckBox, QColorDialog, QFrame
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor

import config_manager as cfg_mgr


# Available activation key options
KEY_OPTIONS = ["super", "alt", "ctrl", "shift"]


class ColorButton(QPushButton):
    """A button that displays and lets the user pick a color."""

    def __init__(self, color=None, parent=None):
        super().__init__(parent)
        self.setFixedSize(50, 26)
        self._color = QColor(*(color or [128, 128, 128, 255]))
        self._update_style()
        self.clicked.connect(self._pick_color)

    def _update_style(self):
        r, g, b, a = self._color.red(), self._color.green(), self._color.blue(), self._color.alpha()
        self.setStyleSheet(
            f"QPushButton {{ background-color: rgba({r},{g},{b},{a}); border: 1px solid #888; border-radius: 3px; }}"
            f"QPushButton:hover {{ background-color: rgba({r},{g},{b},{a}); }}"
        )

    def _pick_color(self):
        color = QColorDialog.getColor(
            self._color, self, "Select Color",
            QColorDialog.ShowAlphaChannel
        )
        if color.isValid():
            self._color = color
            self._update_style()

    def get_rgba(self):
        return [self._color.red(), self._color.green(), self._color.blue(), self._color.alpha()]


class SettingsDialog(QDialog):
    """Dialog to configure application settings."""

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Quick Access Wheel Settings")
        self.setMinimumWidth(460)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self._config = config
        self._settings = cfg_mgr.get_settings(config)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # ── Activation keys ──────────────────────────────────────
        keys_group = QGroupBox("Activation Keys")
        keys_layout = QFormLayout(keys_group)

        self._key1_combo = QComboBox()
        self._key1_combo.addItems([k.capitalize() for k in KEY_OPTIONS])
        self._key2_combo = QComboBox()
        self._key2_combo.addItems([k.capitalize() for k in KEY_OPTIONS])

        current_keys = self._settings.get("activation_keys", ["super", "alt"])
        key1 = current_keys[0] if len(current_keys) > 0 else "super"
        key2 = current_keys[1] if len(current_keys) > 1 else "alt"
        self._key1_combo.setCurrentIndex(KEY_OPTIONS.index(key1) if key1 in KEY_OPTIONS else 0)
        self._key2_combo.setCurrentIndex(KEY_OPTIONS.index(key2) if key2 in KEY_OPTIONS else 1)

        keys_layout.addRow("Key 1:", self._key1_combo)
        keys_layout.addRow("Key 2:", self._key2_combo)

        note = QLabel("Hold both keys to activate the wheel. Changes take effect on restart.")
        note.setWordWrap(True)
        note.setStyleSheet("color: #999; font-size: 11px;")
        keys_layout.addRow(note)

        layout.addWidget(keys_group)

        # ── Timing ───────────────────────────────────────────────
        timing_group = QGroupBox("Timing")
        timing_layout = QFormLayout(timing_group)

        self._dwell_spin = QSpinBox()
        self._dwell_spin.setRange(100, 2000)
        self._dwell_spin.setSuffix(" ms")
        self._dwell_spin.setSingleStep(50)
        self._dwell_spin.setValue(self._settings.get("folder_dwell_ms", 400))
        timing_layout.addRow("Folder/Back hover delay:", self._dwell_spin)

        self._extra_dwell_spin = QSpinBox()
        self._extra_dwell_spin.setRange(0, 2000)
        self._extra_dwell_spin.setSuffix(" ms")
        self._extra_dwell_spin.setSingleStep(50)
        self._extra_dwell_spin.setValue(self._settings.get("auto_continue_extra_ms", 200))
        self._extra_dwell_spin.setToolTip(
            "Extra delay added when auto-continuing into nested folders,\n"
            "giving you time to read the new folder before going deeper."
        )
        timing_layout.addRow("Auto-continue extra delay:", self._extra_dwell_spin)

        layout.addWidget(timing_group)

        # ── Styling ──────────────────────────────────────────────
        style_group = QGroupBox("Styling")
        style_layout = QFormLayout(style_group)

        self._radius_spin = QSpinBox()
        self._radius_spin.setRange(100, 400)
        self._radius_spin.setSuffix(" px")
        self._radius_spin.setValue(self._settings.get("wheel_radius", 180))
        style_layout.addRow("Wheel radius:", self._radius_spin)

        self._inner_spin = QSpinBox()
        self._inner_spin.setRange(20, 100)
        self._inner_spin.setSuffix(" px")
        self._inner_spin.setValue(self._settings.get("inner_radius", 50))
        style_layout.addRow("Inner radius:", self._inner_spin)

        self._opacity_slider = QSlider(Qt.Horizontal)
        self._opacity_slider.setRange(50, 255)
        self._opacity_slider.setValue(self._settings.get("bg_opacity", 220))
        style_layout.addRow("Background opacity:", self._opacity_slider)

        self._font_spin = QSpinBox()
        self._font_spin.setRange(6, 18)
        self._font_spin.setSuffix(" pt")
        self._font_spin.setValue(self._settings.get("font_size", 9))
        style_layout.addRow("Font size:", self._font_spin)

        # Color buttons
        self._segment_color_btn = ColorButton(self._settings.get("segment_color", [50, 50, 55, 200]))
        style_layout.addRow("Segment color:", self._segment_color_btn)

        self._hover_color_btn = ColorButton(self._settings.get("hover_color", [80, 120, 200, 200]))
        style_layout.addRow("Hover color:", self._hover_color_btn)

        self._text_color_btn = ColorButton(self._settings.get("text_color", [220, 220, 220, 255]))
        style_layout.addRow("Text color:", self._text_color_btn)

        self._border_color_btn = ColorButton(self._settings.get("border_color", [100, 100, 110, 180]))
        style_layout.addRow("Border color:", self._border_color_btn)

        layout.addWidget(style_group)

        # ── Buttons ──────────────────────────────────────────────
        btn_layout = QHBoxLayout()

        reload_btn = QPushButton("Reload Config from Disk")
        reload_btn.setToolTip("Re-read config.json if you edited it in a text editor")
        reload_btn.clicked.connect(self._reload_config)
        btn_layout.addWidget(reload_btn)

        btn_layout.addStretch()

        defaults_btn = QPushButton("Reset to Defaults")
        defaults_btn.clicked.connect(self._reset_defaults)
        btn_layout.addWidget(defaults_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Save")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

    def _reload_config(self):
        """Reload config.json from disk and close dialog so the app picks up changes."""
        fresh = cfg_mgr.load_config()
        # Replace the contents of the shared config dict in-place
        self._config.clear()
        self._config.update(fresh)
        self._reloaded = True
        self.accept()

    def _reset_defaults(self):
        defaults = cfg_mgr.default_settings()
        self._key1_combo.setCurrentIndex(KEY_OPTIONS.index(defaults["activation_keys"][0]))
        self._key2_combo.setCurrentIndex(KEY_OPTIONS.index(defaults["activation_keys"][1]))
        self._dwell_spin.setValue(defaults["folder_dwell_ms"])
        self._extra_dwell_spin.setValue(defaults["auto_continue_extra_ms"])
        self._radius_spin.setValue(defaults["wheel_radius"])
        self._inner_spin.setValue(defaults["inner_radius"])
        self._opacity_slider.setValue(defaults["bg_opacity"])
        self._font_spin.setValue(defaults["font_size"])
        self._segment_color_btn._color = QColor(*defaults["segment_color"])
        self._segment_color_btn._update_style()
        self._hover_color_btn._color = QColor(*defaults["hover_color"])
        self._hover_color_btn._update_style()
        self._text_color_btn._color = QColor(*defaults["text_color"])
        self._text_color_btn._update_style()
        self._border_color_btn._color = QColor(*defaults["border_color"])
        self._border_color_btn._update_style()

    def _on_save(self):
        self._settings["activation_keys"] = [
            KEY_OPTIONS[self._key1_combo.currentIndex()],
            KEY_OPTIONS[self._key2_combo.currentIndex()],
        ]
        self._settings["folder_dwell_ms"] = self._dwell_spin.value()
        self._settings["auto_continue_extra_ms"] = self._extra_dwell_spin.value()
        self._settings["wheel_radius"] = self._radius_spin.value()
        self._settings["inner_radius"] = self._inner_spin.value()
        self._settings["bg_opacity"] = self._opacity_slider.value()
        self._settings["font_size"] = self._font_spin.value()
        self._settings["segment_color"] = self._segment_color_btn.get_rgba()
        self._settings["hover_color"] = self._hover_color_btn.get_rgba()
        self._settings["text_color"] = self._text_color_btn.get_rgba()
        self._settings["border_color"] = self._border_color_btn.get_rgba()

        self._config["settings"] = self._settings
        cfg_mgr.save_config(self._config)
        self.accept()
