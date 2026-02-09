from pynput import keyboard
from PyQt5.QtCore import QObject, pyqtSignal, QThread


class HotkeyThread(QThread):
    """Runs the pynput keyboard listener in a background thread."""

    activated = pyqtSignal()
    deactivated = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._super_held = False
        self._alt_held = False
        self._active = False
        self._listener = None

    def run(self):
        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release
        )
        self._listener.start()
        self._listener.join()

    def stop(self):
        if self._listener:
            self._listener.stop()
        self.quit()
        self.wait()

    def _on_press(self, key):
        if key in (keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r):
            self._super_held = True
        elif key in (keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r):
            self._alt_held = True

        if self._super_held and self._alt_held and not self._active:
            self._active = True
            self.activated.emit()

    def _on_release(self, key):
        if key in (keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r):
            self._super_held = False
        elif key in (keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r):
            self._alt_held = False

        if self._active and (not self._super_held or not self._alt_held):
            self._active = False
            self.deactivated.emit()
