"""Linear type for Select (ListBox) parameters."""
from __future__ import annotations


class Linear:
    """Type annotation + default value for Select (ListBox) parameters.

    Usage:
        param: Linear = Linear("opt1", "opt2", "opt3")
    Or:
        param: Linear["opt1", "opt2", "opt3"]
    """

    def __init__(self, *options: str):
        self.options = list(options)

    def __class_getitem__(cls, item):
        if isinstance(item, tuple):
            return cls(*item)
        return cls(item)

    def __repr__(self) -> str:
        return f"Linear({', '.join(repr(o) for o in self.options)})"
