# Macro Tool

> ⚠️ **Work in progress.** Features and file formats may change without notice.

A desktop macro recorder and editor for Windows. Record mouse and keyboard
input, fine-tune the result in a visual editor (or build a macro from scratch),
and play it back on demand. Inspired by classic keystroke recorders, with the
added ability to edit and hand-craft macros rather than only replay them.

## Features

- **Record** mouse movement, clicks, drags, scrolling, and keystrokes.
- **Edit** recorded macros in a visual editor — reorder, tweak, and configure
  individual actions.
- **Build from scratch** by dragging action blocks into the macro.
- **Play back** with a configurable repeat count or continuous looping.
- **Global hotkeys** for record and play, usable while other windows are focused.
- **Save and open** macros as `.json` files.

## Requirements

- Python 3.10 or newer
- Windows

### Dependencies

- [PySide6](https://pypi.org/project/PySide6/) — Qt-based GUI
- [PyAutoGUI](https://pypi.org/project/PyAutoGUI/) — input playback
- [pynput](https://pypi.org/project/pynput/) — input recording and global hotkeys

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd <repository-directory>

# (Recommended) create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate

# Install dependencies
pip install PySide6 pyautogui pynput
```

## Usage

Run the application:

```bash
python main.py
```

The toolbar exposes the core actions:

| Button   | Action                                                        |
| -------- | ------------------------------------------------------------- |
| Open     | Load a macro from a `.json` file.                             |
| Save     | Save the current macro to a `.json` file.                     |
| Record   | Start/stop recording your input into a new macro.             |
| Play     | Play/stop the current macro.                                  |
| Editor   | Show/hide the editor panel to inspect and edit the macro.     |
| Settings | Configure hotkeys and preferences.                            |

### Default hotkeys

| Key  | Action |
| ---- | ------ |
| `F9` | Record |
| `F10`| Play   |

Hotkeys can be reassigned under **Settings → Hotkeys…**.

### Supported actions

Click, repeat-click, cursor move, click-and-drag, wait, key press, hotkey
(key combination), type text, hold key, and scroll.

## Project structure

```
main.py                  Application entry point
engine/                  Recording, playback, and macro file logic
  actions.py             Action types and (de)serialization
  recorder.py            Captures raw input events
  precision_translator.py  Converts recorded events into editable actions
  player.py              Plays a macro back
  macro_file.py          Saves/loads macros as JSON
gui/                     PySide6 user interface
  main_window.py         Main window and toolbar
  widgets/               Editor panels and macro list
  dialogs/               Hotkey and preferences dialogs
tests.py                 Unit tests
```

## Running tests

```bash
python tests.py
```

## Roadmap

- Playback speed control
- Additional editor conveniences
- Cross-platform support

## License

No license has been chosen yet.
