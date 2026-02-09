#!/usr/bin/env python3
"""Quick Access Wheel — a configurable radial action menu triggered by Super+Alt."""

import sys
import os

from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QAction
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor
from PyQt5.QtCore import Qt, QTimer

import config_manager as cfg_mgr
from wheel_widget import WheelWidget
from hotkey_listener import HotkeyThread
from action_dialog import ActionDialog
from action_executor import execute_keystroke, execute_command, execute_launch


class QuickAccessWheel:
    def __init__(self, app):
        self.app = app
        self.config = cfg_mgr.load_config()
        self.folder_stack = []  # list of folder keys; empty = root
        self._selected_folder = None  # snapshot of folder at time of release
        self.wheel = WheelWidget()
        self.wheel.slot_selected.connect(self._on_slot_selected)
        self.wheel.slot_clicked.connect(self._configure_slot)
        self.wheel.folder_hovered.connect(self._on_folder_hovered)

        self._setup_hotkey()
        self._setup_tray()
        self._refresh_wheel()

    # ── Tray icon ───────────────────────────────────────────────
    def _setup_tray(self):
        # Create a simple colored circle icon
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor(80, 120, 200))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(2, 2, 28, 28)
        painter.end()

        self.tray = QSystemTrayIcon(QIcon(pixmap))
        menu = QMenu()
        quit_action = QAction("Quit")
        quit_action.triggered.connect(self._quit)
        menu.addAction(quit_action)
        self.tray.setContextMenu(menu)
        self.tray.setToolTip("Quick Access Wheel (Super+Alt)")
        self.tray.show()

    # ── Hotkey ──────────────────────────────────────────────────
    def _setup_hotkey(self):
        self.hotkey = HotkeyThread()
        self.hotkey.activated.connect(self._show_wheel)
        self.hotkey.deactivated.connect(self._hide_wheel)
        self.hotkey.start()

    def _show_wheel(self):
        self.folder_stack = []
        self._selected_folder = None
        self._refresh_wheel()
        self.wheel.show_at_cursor()

    def _hide_wheel(self):
        # Snapshot which folder we're in before hide triggers slot_selected
        self._selected_folder = self._current_folder()
        self.wheel.hide()

    # ── Wheel data ──────────────────────────────────────────────
    def _current_folder_key(self):
        return self.folder_stack[-1] if self.folder_stack else None

    def _current_folder_path(self):
        return list(self.folder_stack)

    def _current_folder(self):
        path = self._current_folder_path()
        return cfg_mgr.get_folder(self.config, path)

    def _refresh_wheel(self):
        folder = self._current_folder()
        if folder is None:
            folder = cfg_mgr.get_folder(self.config, [])
            self.folder_stack = []
        self.wheel.set_slots(folder["slots"])
        self.wheel.update()

    # ── Slot selection (on Super+Alt release) ───────────────────
    def _on_slot_selected(self, index):
        folder = self._selected_folder
        if folder is None:
            return

        slot = folder["slots"][index]
        action_type = slot.get("type")

        if action_type is None:
            self._configure_slot(index)
        elif action_type == "back":
            # back on release just pops (also handled by hover, but keep as safety)
            if self.folder_stack:
                self.folder_stack.pop()
                self._refresh_wheel()
        elif action_type == "folder":
            # Folders auto-expand on hover, so release on a folder is a no-op
            pass
        elif action_type == "keystroke":
            # Delay keystroke so Super+Alt are fully released first
            value = slot["value"]
            QTimer.singleShot(150, lambda v=value: execute_keystroke(v))
        elif action_type == "command":
            execute_command(slot["value"])
        elif action_type == "launch":
            execute_launch(slot["value"])

    # ── Folder hover auto-expand ─────────────────────────────
    def _on_folder_hovered(self, index):
        """Auto-expand a folder when hovered for long enough."""
        folder = self._current_folder()
        if folder is None:
            return
        slot = folder["slots"][index]
        if slot.get("type") == "folder":
            subfolder_id = slot.get("value")
            if subfolder_id:
                if subfolder_id not in self.config:
                    cfg_mgr.create_subfolder(self.config, subfolder_id)
                self.folder_stack.append(subfolder_id)
                self._refresh_wheel()
        elif slot.get("type") == "back":
            if self.folder_stack:
                self.folder_stack.pop()
                self._refresh_wheel()

    def _configure_slot(self, index):
        folder = self._current_folder()
        slot = folder["slots"][index]

        # Don't allow reconfiguring the back button
        if slot.get("type") == "back":
            return

        dialog = ActionDialog(slot)
        if dialog.exec_() and dialog.result_data is not None:
            data = dialog.result_data

            if data["type"] == "folder":
                folder_id = f"folder_{os.urandom(4).hex()}"
                folder["slots"][index] = {
                    "label": data["label"],
                    "type": "folder",
                    "value": folder_id,
                }
                cfg_mgr.create_subfolder(self.config, folder_id)
            else:
                folder["slots"][index] = data

            cfg_mgr.save_config(self.config)
            self._refresh_wheel()

    # ── Cleanup ─────────────────────────────────────────────────
    def _quit(self):
        self.hotkey.stop()
        self.tray.hide()
        self.app.quit()


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    wheel_app = QuickAccessWheel(app)
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
