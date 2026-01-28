"""Dynamic symbol loading from dotted paths."""

from __future__ import annotations

import importlib
from typing import Any

from .errors import (
    import_invalid_format,
    import_module_not_found,
    import_symbol_not_found,
)


def load_symbol(dotted: str) -> Any:
    """
    Load a symbol from 'package.module:SymbolName'.

    Args:
        dotted: A string in the format 'module.path:SymbolName'

    Returns:
        The loaded symbol (class, function, etc.)

    Raises:
        ImportError_: If the format is invalid, module can't be imported,
                      or symbol doesn't exist in the module.
    """
    if ":" not in dotted:
        raise import_invalid_format(dotted)

    module_path, symbol_name = dotted.split(":", 1)
    module_path = module_path.strip()
    symbol_name = symbol_name.strip()

    if not module_path or not symbol_name:
        raise import_invalid_format(dotted)

    try:
        module = importlib.import_module(module_path)
    except Exception:
        raise import_module_not_found(module_path, dotted) from None

    try:
        return getattr(module, symbol_name)
    except AttributeError:
        raise import_symbol_not_found(module_path, symbol_name, dotted) from None
