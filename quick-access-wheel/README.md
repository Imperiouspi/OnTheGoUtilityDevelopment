# Quick Access Wheel

A configurable radial action wheel that appears when you hold **Super+Alt**. Move your mouse to select one of 8 slots, then release to execute the action.

## Features

- **Radial wheel overlay** appears at your cursor when Super+Alt is held
- **8 configurable slots** per wheel
- **Nested folders** — any slot can open a sub-wheel with 8 more actions
- **Action types:**
  - **Keystroke** — simulate a key combination
  - **Shell command** — run a command invisibly in the background
  - **Launch program** — open an application
  - **Folder** — open a nested sub-wheel
- Click an unconfigured slot to open the configuration dialog
- Config persists in `config.json`

## Requirements

- Python 3.7+
- PyQt5
- pynput
- Linux with X11

## Installation

```bash
cd quick-access-wheel
pip install -r requirements.txt
```

## Usage

```bash
python main.py
```

Hold **Super+Alt** to show the wheel at your cursor. Move the mouse over a segment and release to select it. A system tray icon is added for quitting the app.

Unconfigured slots show "Select to add action" — select one to open the configuration dialog and assign a keystroke, command, program, or sub-folder.
