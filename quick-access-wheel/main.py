#!/usr/bin/env python3
"""Quick Access Wheel — a configurable radial action menu triggered by Super+Alt."""

import sys
import os

from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QAction, QMessageBox, QInputDialog
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor
from PyQt5.QtCore import Qt, QTimer

import config_manager as cfg_mgr
from wheel_widget import WheelWidget
from hotkey_listener import HotkeyThread
from action_dialog import ActionDialog
from action_executor import execute_keystroke, execute_command, execute_launch
from settings_dialog import SettingsDialog


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
        self.wheel.settings_selected.connect(self._open_settings)

        self._setup_hotkey()
        self._setup_tray()
        self._apply_settings()
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
        settings_action = QAction("Settings")
        settings_action.triggered.connect(self._open_settings)
        menu.addAction(settings_action)
        quit_action = QAction("Quit")
        quit_action.triggered.connect(self._quit)
        menu.addAction(quit_action)
        self.tray.setContextMenu(menu)
        self.tray.setToolTip("Quick Access Wheel (Super+Alt)")
        self.tray.show()

    # ── Settings ─────────────────────────────────────────────────
    def _apply_settings(self):
        """Apply current settings to all components."""
        settings = cfg_mgr.get_settings(self.config)
        self.wheel.apply_settings(settings)

    def _open_settings(self):
        """Open the settings dialog."""
        dialog = SettingsDialog(self.config)
        if dialog.exec_():
            self._apply_settings()
            self._refresh_wheel()

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

    def _current_folder_slot(self):
        """Slot data for the folder we're currently viewing (from parent). None at root."""
        if not self.folder_stack:
            return None
        parent_path = self.folder_stack[:-1]
        parent = cfg_mgr.get_folder(self.config, parent_path)
        if parent is None:
            return None
        folder_id = self.folder_stack[-1]
        for slot in parent["slots"]:
            if slot.get("type") == "folder" and slot.get("value") == folder_id:
                return slot
        return {"label": "Folder", "show_label": True}

    def _refresh_wheel(self):
        folder = self._current_folder()
        if folder is None:
            folder = cfg_mgr.get_folder(self.config, [])
            self.folder_stack = []
        self.wheel.set_slots(folder["slots"])
        self.wheel.set_centre_slot(self._current_folder_slot())
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
                # Reset hover so the wheel re-evaluates the mouse position
                # in the new folder — enables auto-continuation without
                # requiring the user to move the mouse back to the centre.
                self.wheel.reset_hover()
        elif slot.get("type") == "back":
            if self.folder_stack:
                self.folder_stack.pop()
                self._refresh_wheel()
                self.wheel.reset_hover()

    # ── Folder management helpers ─────────────────────────────
    def _collect_referenced_folders(self):
        """Return set of all folder IDs that are referenced by a slot somewhere."""
        referenced = set()
        for key, value in self.config.items():
            if key in ("settings",):
                continue
            if isinstance(value, dict) and "slots" in value:
                for slot in value["slots"]:
                    if slot.get("type") == "folder" and slot.get("value"):
                        referenced.add(slot["value"])
        return referenced

    def _collect_all_folder_keys(self):
        """Return set of all folder_* keys in config."""
        return {k for k in self.config if k.startswith("folder_")}

    def _find_orphaned_folders(self):
        """Return folder IDs that exist in config but aren't referenced by any slot."""
        all_folders = self._collect_all_folder_keys()
        referenced = self._collect_referenced_folders()
        return all_folders - referenced

    def _remove_folder_recursive(self, folder_id):
        """Remove a folder and all its unreferenced sub-folders from config."""
        folder_data = self.config.get(folder_id)
        if folder_data is None:
            return
        # Collect sub-folder IDs before removing
        sub_ids = []
        for slot in folder_data.get("slots", []):
            if slot.get("type") == "folder" and slot.get("value"):
                sub_ids.append(slot["value"])
        # Remove this folder
        del self.config[folder_id]
        # Recursively remove sub-folders
        for sub_id in sub_ids:
            if sub_id in self.config:
                self._remove_folder_recursive(sub_id)

    def _configure_slot(self, index):
        folder = self._current_folder()
        slot = folder["slots"][index]

        # Don't allow reconfiguring the back button
        if slot.get("type") == "back":
            return

        old_type = slot.get("type")
        old_folder_id = slot.get("value") if old_type == "folder" else None

        dialog = ActionDialog(slot)
        if dialog.exec_() and dialog.result_data is not None:
            data = dialog.result_data

            # If removing a folder slot, ask whether to delete the subfolder data
            if old_folder_id and (data["type"] != "folder" or data.get("value") != old_folder_id):
                reply = QMessageBox.question(
                    None, "Remove Folder Data",
                    "The folder was removed from this slot.\n"
                    "Do you also want to remove its saved contents from the config?\n\n"
                    "Choose 'No' to keep the data (you can restore it later).",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )
                if reply == QMessageBox.Yes:
                    self._remove_folder_recursive(old_folder_id)

            if data["type"] == "folder":
                # Check for orphaned folders that could be restored
                orphaned = self._find_orphaned_folders()
                folder_id = None
                if orphaned:
                    # Build a list of orphaned folder labels for the user to choose
                    choices = []
                    orphan_list = sorted(orphaned)
                    for oid in orphan_list:
                        fdata = self.config.get(oid, {})
                        slot_labels = [s.get("label", "?") for s in fdata.get("slots", [])
                                       if s.get("type") and s.get("type") != "back"]
                        desc = ", ".join(slot_labels[:3]) if slot_labels else "(empty)"
                        choices.append(f"{oid}  [{desc}]")
                    choices.insert(0, "(Create new empty folder)")

                    choice, ok = QInputDialog.getItem(
                        None, "Restore Folder?",
                        "There are saved folders not currently in use.\n"
                        "Would you like to restore one, or create a new folder?",
                        choices, 0, False,
                    )
                    if ok and choice != "(Create new empty folder)":
                        # Extract folder ID from the choice string
                        folder_id = choice.split()[0]

                if not folder_id:
                    folder_id = f"folder_{os.urandom(4).hex()}"
                    cfg_mgr.create_subfolder(self.config, folder_id)

                folder["slots"][index] = {
                    "label": data["label"],
                    "type": "folder",
                    "value": folder_id,
                    "icon": data.get("icon"),
                    "icon_type": data.get("icon_type"),
                    "show_label": data.get("show_label", True),
                }
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
