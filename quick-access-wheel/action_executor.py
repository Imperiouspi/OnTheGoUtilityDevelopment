import subprocess
from pynput.keyboard import Controller, Key, HotKey


_keyboard = Controller()

# Map modifier names from QKeySequence.toString() to pynput keys
_MODIFIER_MAP = {
    "Ctrl": Key.ctrl,
    "Shift": Key.shift,
    "Alt": Key.alt,
    "Meta": Key.cmd,
}

# Map special key names (from config) to pynput Key enum
_SPECIAL_KEY_MAP = {
    "space": Key.space,
    "enter": Key.enter,
    "return": Key.enter,
    "tab": Key.tab,
    "escape": Key.esc,
    "esc": Key.esc,
    "backspace": Key.backspace,
}


def _parse_key_sequence(seq_str):
    """Parse a QKeySequence string like 'Ctrl+Shift+A' into pynput keys."""
    parts = seq_str.split("+")
    modifiers = []
    key_char = None

    for part in parts:
        part = part.strip()
        if part in _MODIFIER_MAP:
            modifiers.append(_MODIFIER_MAP[part])
        else:
            key_char = part.lower() if len(part) == 1 else part
            key_char = _SPECIAL_KEY_MAP.get(key_char.lower() if isinstance(key_char, str) else key_char, key_char)

    return modifiers, key_char


def execute_keystroke(seq_str):
    """Simulate a key combination."""
    modifiers, key_char = _parse_key_sequence(seq_str)

    for mod in modifiers:
        _keyboard.press(mod)
    if key_char:
        _keyboard.press(key_char)
        _keyboard.release(key_char)
    for mod in reversed(modifiers):
        _keyboard.release(mod)


def execute_command(cmd):
    """Run a shell command invisibly in the background."""
    subprocess.Popen(
        cmd,
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )


def execute_launch(program_path):
    """Launch a program."""
    subprocess.Popen(
        [program_path],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )
