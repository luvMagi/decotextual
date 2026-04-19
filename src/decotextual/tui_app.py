"""Main Textual TUI application."""
from __future__ import annotations

import inspect
import io
import logging
import queue
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, get_origin

from rich.text import Text as RichText
from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    RichLog,
    Select,
    Static,
    TextArea,
    Tree,
)
from textual.widgets.tree import TreeNode

from ._linear import Linear
from .decorators import get_registry


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class MethodData:
    cls: type
    method_name: str
    meta: dict  # {"name": ..., "description": ..., "placeholders": ...}


# ---------------------------------------------------------------------------
# Helper I/O classes
# ---------------------------------------------------------------------------

class _QueueWriter(io.TextIOBase):
    def __init__(self, q: queue.Queue):
        self._q = q

    def write(self, text: str) -> int:
        if text and text.strip():
            self._q.put(text)
        return len(text)

    def flush(self) -> None:
        pass


class _QueueHandler(logging.Handler):
    def __init__(self, q: queue.Queue):
        super().__init__()
        self._q = q

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._q.put(self.format(record))
        except Exception:
            self.handleError(record)


# ---------------------------------------------------------------------------
# Main App
# ---------------------------------------------------------------------------

class ToolkitApp(App):
    CSS = """
Screen { layout: vertical; }

#body { height: 1fr; }

#tool-tree { width: 28; border-right: solid $accent; }

#right-side { width: 1fr; layout: vertical; }

#form-panel { height: 2fr; layout: vertical; border-bottom: solid $accent; }

#method-header {
    height: 3;
    background: $boost;
    padding: 1;
    text-style: bold;
}

#method-desc {
    height: auto;
    max-height: 4;
    padding: 0 1;
    color: $text-muted;
}

#form-area { height: 1fr; padding: 0 1; }
#form-area Label { margin-top: 1; }
#form-area Input { margin-bottom: 1; }
#form-area Select { margin-bottom: 1; }
#form-area TextArea { height: 5; margin-bottom: 1; }

#button-bar {
    height: 3;
    align: left middle;
    padding: 0 1;
    border-top: solid $surface-darken-1;
}
#run-btn { margin-right: 1; min-width: 10; content-align: center middle; }
#stop-btn { min-width: 10; content-align: center middle; }

#log-panel { height: 1fr; min-height: 8; layout: vertical; }

#log-toolbar {
    height: 3;
    align: right middle;
    padding: 0 1;
    background: $boost;
}
#copy-log-btn { min-width: 20; content-align: center middle; }

#log { height: 1fr; }
"""

    BINDINGS = [("q", "quit", "Quit")]

    def __init__(self):
        super().__init__()
        self._current_method_data: MethodData | None = None
        self._form_params: list[tuple[str, Any, str]] = []  # (name, widget, type_hint)
        self._instances: dict[type, Any] = {}
        self._log_queue: queue.Queue = queue.Queue()
        self._log_buffer: list[str] = []
        self._stop_requested = False

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="body"):
            yield Tree("Toolkit", id="tool-tree")
            with Vertical(id="right-side"):
                with Vertical(id="form-panel"):
                    yield Static("← Select a method from the left", id="method-header")
                    yield Static("", id="method-desc")
                    yield VerticalScroll(id="form-area")
                    with Horizontal(id="button-bar"):
                        yield Button("▶ Run", id="run-btn", variant="success", disabled=True)
                        yield Button("■ Stop", id="stop-btn", variant="error", disabled=True)
                with Vertical(id="log-panel"):
                    with Horizontal(id="log-toolbar"):
                        yield Button("⎘ Copy Log", id="copy-log-btn", variant="default")
                    yield RichLog(id="log", highlight=True, markup=True)
        yield Footer()

    def on_mount(self) -> None:
        tree: Tree = self.query_one("#tool-tree", Tree)
        tree.root.expand()

        categories: dict[str, dict[str, list[tuple]]] = {}
        for cls in get_registry():
            cat = getattr(cls, "_tui_category", "Uncategorized")
            tool_name = getattr(cls, "_tui_tool_name", cls.__name__)
            if cat not in categories:
                categories[cat] = {}
            if tool_name not in categories[cat]:
                categories[cat][tool_name] = []

            for attr_name in dir(cls):
                try:
                    method = getattr(cls, attr_name)
                except Exception:
                    continue
                if callable(method) and hasattr(method, "_tui_method_meta"):
                    categories[cat][tool_name].append((cls, attr_name, method._tui_method_meta))

        for cat_name, tools in categories.items():
            cat_node: TreeNode = tree.root.add(cat_name, expand=True)
            for tool_name, methods in tools.items():
                tool_node: TreeNode = cat_node.add(tool_name, expand=True)
                for cls, method_name, meta in methods:
                    tool_node.add_leaf(
                        meta["name"],
                        data=MethodData(cls=cls, method_name=method_name, meta=meta),
                    )

        self.set_interval(0.1, self._drain_log_queue)

    # ------------------------------------------------------------------
    # Tree selection
    # ------------------------------------------------------------------

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        node = event.node
        if not isinstance(node.data, MethodData):
            return

        method_data: MethodData = node.data
        self._current_method_data = method_data
        self._build_form(method_data)

        self.query_one("#method-header", Static).update(method_data.meta["name"])
        self.query_one("#method-desc", Static).update(method_data.meta.get("description", ""))
        self.query_one("#run-btn", Button).disabled = False
        self.query_one("#stop-btn", Button).disabled = True

    # ------------------------------------------------------------------
    # Form building
    # ------------------------------------------------------------------

    def _build_form(self, method_data: MethodData) -> None:
        form_area = self.query_one("#form-area", VerticalScroll)
        for widget in list(form_area.query("*")):
            widget.remove()

        self._form_params = []

        placeholders: dict = method_data.meta.get("placeholders") or {}

        try:
            method = getattr(method_data.cls, method_data.method_name)
            sig = inspect.signature(method)
        except Exception:
            return

        widgets_to_mount = []

        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue

            annotation = param.annotation
            default = param.default
            placeholder = placeholders.get(param_name, f"Enter {param_name}...")

            label = Label(f"{param_name}:")

            if isinstance(default, Linear):
                options = [(opt, opt) for opt in default.options]
                widget = Select(options, id=f"param_{param_name}")
                type_hint = "linear"

            elif annotation is list or get_origin(annotation) is list:
                widget = TextArea("", id=f"param_{param_name}")
                type_hint = "list"

            elif annotation is Path:
                value = str(default) if default is not inspect.Parameter.empty else ""
                widget = Input(placeholder=placeholder, value=value, id=f"param_{param_name}")
                type_hint = "path"

            elif annotation is int:
                value = str(default) if default is not inspect.Parameter.empty else ""
                widget = Input(placeholder=placeholder, value=value, id=f"param_{param_name}")
                type_hint = "int"

            elif annotation is float:
                value = str(default) if default is not inspect.Parameter.empty else ""
                widget = Input(placeholder=placeholder, value=value, id=f"param_{param_name}")
                type_hint = "float"

            else:
                value = "" if default is inspect.Parameter.empty or default is None else str(default)
                widget = Input(placeholder=placeholder, value=value, id=f"param_{param_name}")
                type_hint = "str"

            widgets_to_mount.append(label)
            widgets_to_mount.append(widget)
            self._form_params.append((param_name, widget, type_hint))

        if widgets_to_mount:
            form_area.mount(*widgets_to_mount)

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "run-btn":
            self._run_method()
        elif event.button.id == "stop-btn":
            self._stop_requested = True
        elif event.button.id == "copy-log-btn":
            self._copy_log()

    def _copy_log(self) -> None:
        if not self._log_buffer:
            self.notify("Log is empty", severity="warning")
            return
        text = "\n".join(self._log_buffer)
        try:
            self.copy_to_clipboard(text)
            self.notify("Log copied to clipboard")
        except Exception as exc:
            self.notify(f"Copy failed: {exc}", severity="error")

    def _run_method(self) -> None:
        if self._current_method_data is None:
            return

        log = self.query_one("#log", RichLog)
        log.clear()
        self._log_buffer.clear()

        kwargs: dict[str, Any] = {}
        for param_name, widget, type_hint in self._form_params:
            try:
                if type_hint == "linear":
                    val = widget.value
                    kwargs[param_name] = None if val is Select.BLANK else val
                elif type_hint == "list":
                    raw: str = widget.text
                    if not raw.strip():
                        kwargs[param_name] = []
                    else:
                        parts = []
                        for line in raw.splitlines():
                            for item in line.split(","):
                                stripped = item.strip()
                                if stripped:
                                    parts.append(stripped)
                        kwargs[param_name] = parts
                elif type_hint == "path":
                    val = widget.value.strip()
                    kwargs[param_name] = Path(val) if val else Path(".")
                elif type_hint == "int":
                    val = widget.value.strip()
                    kwargs[param_name] = int(val) if val else 0
                elif type_hint == "float":
                    val = widget.value.strip()
                    kwargs[param_name] = float(val) if val else 0.0
                else:
                    kwargs[param_name] = widget.value
            except Exception as exc:
                log.write(f"[red]Failed to parse param {param_name!r}: {exc}[/red]")
                return

        self.query_one("#run-btn", Button).disabled = True
        self.query_one("#stop-btn", Button).disabled = False
        self._stop_requested = False

        self._execute_method(
            cls=self._current_method_data.cls,
            method_name=self._current_method_data.method_name,
            kwargs=kwargs,
        )

    # ------------------------------------------------------------------
    # Worker
    # ------------------------------------------------------------------

    @work(thread=True)
    def _execute_method(self, cls: type, method_name: str, kwargs: dict) -> None:
        instance = self._instances.setdefault(cls, cls())
        method = getattr(instance, method_name)

        old_stdout = sys.stdout
        sys.stdout = _QueueWriter(self._log_queue)

        handler = _QueueHandler(self._log_queue)
        handler.setFormatter(logging.Formatter("[%(levelname)s] %(name)s: %(message)s"))
        root_logger = logging.getLogger()
        old_level = root_logger.level
        if root_logger.level == logging.NOTSET or root_logger.level > logging.DEBUG:
            root_logger.setLevel(logging.DEBUG)
        root_logger.addHandler(handler)

        try:
            result = method(**kwargs)
            if result is not None:
                self._log_queue.put(f"[bold green]✓ Result:[/bold green] {result}")
        except Exception as exc:
            self._log_queue.put(f"[bold red]✗ Error:[/bold red] {exc}")
        finally:
            sys.stdout = old_stdout
            root_logger.removeHandler(handler)
            root_logger.setLevel(old_level)
            self.call_from_thread(self._on_method_done)

    def _on_method_done(self) -> None:
        self.query_one("#run-btn", Button).disabled = False
        self.query_one("#stop-btn", Button).disabled = True

    # ------------------------------------------------------------------
    # Log draining
    # ------------------------------------------------------------------

    def _drain_log_queue(self) -> None:
        log = self.query_one("#log", RichLog)
        while True:
            try:
                msg = self._log_queue.get_nowait()
                log.write(msg)
                self._log_buffer.append(RichText.from_markup(msg).plain)
            except queue.Empty:
                break


# ---------------------------------------------------------------------------
# Entry point helper
# ---------------------------------------------------------------------------

def run_tui() -> None:
    app = ToolkitApp()
    app.run()
