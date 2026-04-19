"""Decorators for registering TUI tools and methods."""
from __future__ import annotations

from typing import Callable

_REGISTRY: list[type] = []


def register_tool(category: str, tool_name: str):
    """Class decorator that registers a class as a TUI tool.

    Args:
        category: The top-level category name shown in the tree.
        tool_name: The second-level tool name shown in the tree.
    """
    def decorator(cls: type) -> type:
        cls._tui_category = category
        cls._tui_tool_name = tool_name
        _REGISTRY.append(cls)
        return cls

    return decorator


def tool_method(name: str, description: str = "", placeholders: dict | None = None):
    """Method decorator that marks a method as a TUI tool method.

    Args:
        name: The display name shown in the third-level tree node.
        description: A brief description shown in the right panel header area.
        placeholders: Optional mapping of param_name -> placeholder text for inputs.
    """
    def decorator(fn: Callable) -> Callable:
        fn._tui_method_meta = {
            "name": name,
            "description": description,
            "placeholders": placeholders or {},
        }
        return fn

    return decorator


def get_registry() -> list[type]:
    """Return a copy of the registered tool classes."""
    return list(_REGISTRY)
