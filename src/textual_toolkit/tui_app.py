"""Main Textual TUI application."""
from __future__ import annotations

import inspect
import io
import logging
import queue
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, get_origin, get_args

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
    """Data stored on leaf tree nodes."""
    cls: type
    method_name: str
    meta: dict  # {"name": ..., "description": ..., "placeholders": ...}


# ---------------------------------------------------------------------------
# Helper I/O classes
# ---------------------------------------------------------------------------

class _QueueWriter(io.TextIOBase):
    """Redirect stdout writes to a queue."""

    def __init__(self, q: queue.Queue):
        self._q = q

    def write(self, text: str) -> int:
        if text and text.strip():
            self._q.put(text)
        return len(text)

    def flush(self) -> None:
        pass


class _QueueHandler(logging.Handler):
    """Send log records to a queue."""

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
    """The main Textual TUI application."""

    CSS = """
Screen { layout: vertical; }
#main { height: 3fr; }
#tool-tree { width: 28; border-right: solid $accent; }
#right-panel { width: 1fr; layout: vertical; }
#method-header { height: 3; background: $boost; padding: 1; text-style: bold; }
#method-desc { height: auto; max-height: 4; padding: 0 1; color: $text-muted; }
#form-area { height: 1fr; padding: 0 1; }
#form-area Label { margin-top: 1; }
#form-area Input { margin-bottom: 1; }
#form-area Select { margin-bottom: 1; }
#form-area TextArea { height: 5; margin-bottom: 1; }
#button-bar { height: 3; align: center middle; border-top: solid $surface-darken-1; }
#run-btn { margin-right: 1; min-width: 10; }
#stop-btn { min-width: 10; }
#log { height: 1fr; min-height: 8; max-height: 14; border-top: solid $accent; }
"""

    BINDINGS = [("q", "quit", "退出")]

    def __init__(self):
        super().__init__()
        self._current_method_data: MethodData | None = None
        self._form_params: list[tuple[str, Any, str]] = []  # (name, widget, type_hint)
        self._instances: dict[type, Any] = {}
        self._log_queue: queue.Queue = queue.Queue()
        self._worker = None
        self._stop_requested = False

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main"):
            yield Tree("工具箱", id="tool-tree")
            with Vertical(id="right-panel"):
                yield Static("← 请在左侧选择一个方法", id="method-header")
                yield Static("", id="method-desc")
                yield VerticalScroll(id="form-area")
                with Horizontal(id="button-bar"):
                    yield Button("▶ 运行", id="run-btn", variant="success", disabled=True)
                    yield Button("■ 停止", id="stop-btn", variant="error", disabled=True)
        yield RichLog(id="log", highlight=True, markup=True)
        yield Footer()

    def on_mount(self) -> None:
        """Build the tool tree from the registry."""
        tree: Tree = self.query_one("#tool-tree", Tree)
        tree.root.expand()

        registry = get_registry()

        # Group: category -> tool_name -> list of (cls, method_name, meta)
        categories: dict[str, dict[str, list[tuple]]] = {}
        for cls in registry:
            cat = getattr(cls, "_tui_category", "未分类")
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

        # Start log drainer
        self.set_interval(0.1, self._drain_log_queue)

    # ------------------------------------------------------------------
    # Tree selection
    # ------------------------------------------------------------------

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Handle tree node selection — only respond to leaf nodes with MethodData."""
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
        """Dynamically build the parameter form for the selected method."""
        form_area = self.query_one("#form-area", VerticalScroll)
        # Remove existing widgets
        for widget in list(form_area.query("*")):
            widget.remove()

        self._form_params = []

        cls = method_data.cls
        method_name = method_data.method_name
        meta = method_data.meta
        placeholders: dict = meta.get("placeholders") or {}

        try:
            method = getattr(cls, method_name)
            sig = inspect.signature(method)
        except Exception:
            return

        widgets_to_mount = []

        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue

            annotation = param.annotation
            default = param.default
            placeholder = placeholders.get(param_name, f"输入 {param_name}...")

            label = Label(f"{param_name}:")

            # Determine widget type
            # 1. Default is a Linear instance → Select widget
            if isinstance(default, Linear):
                options = [(opt, opt) for opt in default.options]
                widget = Select(options, id=f"param_{param_name}")
                type_hint = "linear"

            # 2. Annotation is list or list[...] → TextArea
            elif annotation is list or get_origin(annotation) is list:
                value = ""
                widget = TextArea(value, id=f"param_{param_name}")
                type_hint = "list"

            # 3. Annotation is Path → Input
            elif annotation is Path:
                value = str(default) if default is not inspect.Parameter.empty else ""
                widget = Input(
                    placeholder=placeholder,
                    value=value,
                    id=f"param_{param_name}",
                )
                type_hint = "path"

            # 4. int annotation → Input
            elif annotation is int:
                value = str(default) if default is not inspect.Parameter.empty else ""
                widget = Input(
                    placeholder=placeholder,
                    value=value,
                    id=f"param_{param_name}",
                )
                type_hint = "int"

            # 5. float annotation → Input
            elif annotation is float:
                value = str(default) if default is not inspect.Parameter.empty else ""
                widget = Input(
                    placeholder=placeholder,
                    value=value,
                    id=f"param_{param_name}",
                )
                type_hint = "float"

            # 6. Everything else (str / no annotation) → Input
            else:
                if default is inspect.Parameter.empty or default is None:
                    value = ""
                else:
                    value = str(default)
                widget = Input(
                    placeholder=placeholder,
                    value=value,
                    id=f"param_{param_name}",
                )
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

    def _run_method(self) -> None:
        """Collect form values and launch the worker thread."""
        if self._current_method_data is None:
            return

        # Clear log
        log = self.query_one("#log", RichLog)
        log.clear()

        # Collect kwargs
        kwargs: dict[str, Any] = {}
        for param_name, widget, type_hint in self._form_params:
            try:
                if type_hint == "linear":
                    val = widget.value
                    if val is Select.BLANK:
                        val = None
                    kwargs[param_name] = val
                elif type_hint == "list":
                    raw: str = widget.text
                    if not raw.strip():
                        kwargs[param_name] = []
                    else:
                        # Split by newline first, then comma
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
                log.write(f"[red]参数 {param_name!r} 解析失败: {exc}[/red]")
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
        """Run the tool method in a background thread."""
        instance = self._instances.setdefault(cls, cls())
        method = getattr(instance, method_name)

        # Redirect stdout
        old_stdout = sys.stdout
        sys.stdout = _QueueWriter(self._log_queue)

        # Add logging handler
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
                self._log_queue.put(f"[bold green]✓ 结果:[/bold green] {result}")
        except Exception as exc:
            self._log_queue.put(f"[bold red]✗ 错误:[/bold red] {exc}")
        finally:
            sys.stdout = old_stdout
            root_logger.removeHandler(handler)
            root_logger.setLevel(old_level)
            self.call_from_thread(self._on_method_done)

    def _on_method_done(self) -> None:
        """Called from the worker thread when execution finishes."""
        self.query_one("#run-btn", Button).disabled = False
        self.query_one("#stop-btn", Button).disabled = True

    # ------------------------------------------------------------------
    # Log draining
    # ------------------------------------------------------------------

    def _drain_log_queue(self) -> None:
        """Drain queued log messages into the RichLog widget."""
        log = self.query_one("#log", RichLog)
        while True:
            try:
                msg = self._log_queue.get_nowait()
                log.write(msg)
            except queue.Empty:
                break


# ---------------------------------------------------------------------------
# Entry point helper
# ---------------------------------------------------------------------------

def run_tui() -> None:
    """Launch the TUI application."""
    app = ToolkitApp()
    app.run()
