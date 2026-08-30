from __future__ import annotations

from typing import Any

__all__ = ["DEFAULT_ADAPTER", "get_adapter", "list_adapters"]


def __getattr__(name: str) -> Any:
    if name in __all__:
        from app.adapters import registry

        return getattr(registry, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
