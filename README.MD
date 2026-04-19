# decotextual

A lightweight decorator-based library for building Textual TUI (terminal user interface) tool panels. Define your tool classes and methods with simple decorators, and get a fully functional terminal GUI — no manual widget wiring required.

---

## Features

- **Decorator-driven** — register tools and methods with `@register_tool` and `@tool_method`
- **Auto form generation** — input widgets are created automatically from method signatures (`str`, `int`, `float`, `Path`, `list`)
- **Dropdown support** — use `Linear(...)` as a default value to render a `Select` widget
- **Live log panel** — stdout and logging output is captured and streamed to the built-in log view
- **Copy log** — copy the full log output to the clipboard with one click

---

## Installation

```bash
pip install decotextual
```

> Requires Python 3.10+ and [Textual](https://github.com/Textualize/textual).

---

## Quick Start

```python
from pathlib import Path
import logging
from decotextual import register_tool, tool_method, run_tui, Linear


@register_tool(category="File Tools", tool_name="File Utilities")
class FileTool:

    @tool_method(
        name="Read File",
        description="Read a file and return the first N lines",
        placeholders={
            "file_path": "Full path, e.g. /data/log.txt",
        }
    )
    def read_file(self, file_path: Path, line_count: int = 100):
        logging.info(f"Reading: {file_path}")
        print(f"First {line_count} lines of {file_path}")
        return "Done"

    @tool_method(
        name="Batch Rename",
        description="Batch rename files in a directory",
        placeholders={"directory": "Target directory path"}
    )
    def batch_rename(
        self,
        directory: Path,
        prefix: str = "file_",
        mode: Linear = Linear("Sequential", "Timestamp", "MD5"),
    ):
        print(f"Scanning: {directory}, prefix={prefix}, mode={mode}")
        return "Rename complete"


if __name__ == "__main__":
    run_tui()
```

Run it:

```bash
python your_script.py
```

---

## Decorator Reference

### `@register_tool(category, tool_name)`

Registers a class as a tool in the TUI tree.

| Parameter   | Type  | Description                            |
|-------------|-------|----------------------------------------|
| `category`  | `str` | Top-level group shown in the left tree |
| `tool_name` | `str` | Second-level node under the category   |

### `@tool_method(name, description, placeholders)`

Marks a method as a runnable action in the TUI.

| Parameter      | Type             | Description                                       |
|----------------|------------------|---------------------------------------------------|
| `name`         | `str`            | Display name shown as a leaf node in the tree     |
| `description`  | `str`            | Short description shown in the right panel header |
| `placeholders` | `dict` or `None` | Maps param names to input placeholder strings     |

### `Linear(*options)`

Use as a parameter default to render a `Select` dropdown widget.

```python
mode: Linear = Linear("Option A", "Option B", "Option C")
```

---

## Supported Parameter Types

| Python type        | Widget rendered   |
|--------------------|-------------------|
| `str`              | `Input`           |
| `int`              | `Input` (integer) |
| `float`            | `Input` (float)   |
| `Path`             | `Input` (path)    |
| `list`             | `TextArea`        |
| `Linear` (default) | `Select` dropdown |

> For `list` parameters, values can be entered one per line or comma-separated; both are parsed into a Python list.

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `q` | Quit   |

---

## Project Structure

```
decotextual/
├── src/
│   └── decotextual/
│       ├── __init__.py
│       ├── decorators.py   # @register_tool and @tool_method
│       ├── _linear.py      # Linear dropdown helper
│       ├── tui_app.py      # Textual app and widget layout
│       ├── widgets/
│       └── utils/
├── pyproject.toml
└── README.md
```

---

## License

MIT
