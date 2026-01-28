"""Pack loading and collision detection.

This module provides utilities for loading StatePacks from various sources
and detecting collisions between them.

Key function:
    load_packs(states=None, packs=None, builtins=None) -> list[StatePack]

Collision rules:
    - Duplicate state keys across packs → error
    - Pack key shadows builtin → error
"""

from __future__ import annotations

import importlib
from typing import Any, Dict, List, Optional, Set, Type, Union

from .errors import ConfigError, ErrorContext, ImportError_
from .statepack import MappingPack, StateSpec, StatePack


def _is_statepack_instance(obj: Any) -> bool:
    """Check if object implements StatePack protocol (duck typing).

    Returns False for classes (use _is_statepack_class for those).
    """
    # Exclude classes - we want actual instances
    if isinstance(obj, type):
        return False
    return (
        hasattr(obj, "name")
        and hasattr(obj, "provides")
        and hasattr(obj, "transitions")
        and hasattr(obj, "depends_on")
        and callable(getattr(obj, "provides", None))
        and callable(getattr(obj, "transitions", None))
        and callable(getattr(obj, "depends_on", None))
    )


def _is_statepack_class(cls: Any) -> bool:
    """Check if class implements StatePack protocol when instantiated."""
    if not isinstance(cls, type):
        return False
    # Check that the class has the required methods/properties
    return (
        hasattr(cls, "name")
        and hasattr(cls, "provides")
        and hasattr(cls, "transitions")
        and hasattr(cls, "depends_on")
    )


def _load_pack_from_dotted_path(dotted_path: str) -> StatePack:
    """Load a StatePack from a dotted path.

    Supports:
        - "module.path:PackClass" → instantiates PackClass()
        - "module.path:pack_instance" → uses instance directly

    Args:
        dotted_path: Import path in "module:symbol" format.

    Returns:
        StatePack instance.

    Raises:
        ImportError_: If path format is invalid or import fails.
        ConfigError: If imported object is not a StatePack.
    """
    if ":" not in dotted_path:
        ctx = ErrorContext().add("dotted_path", dotted_path)
        raise ImportError_(
            f"Invalid pack path format: '{dotted_path}'",
            why="Pack paths must use ':' to separate module from symbol.",
            fix="Use format 'mypackage.packs:MyPack' (colon separates module from symbol).",
            context=ctx,
        )

    module_path, symbol_name = dotted_path.split(":", 1)
    module_path = module_path.strip()
    symbol_name = symbol_name.strip()

    if not module_path or not symbol_name:
        ctx = ErrorContext().add("dotted_path", dotted_path)
        raise ImportError_(
            f"Invalid pack path format: '{dotted_path}'",
            why="Both module path and symbol name must be non-empty.",
            fix="Use format 'mypackage.packs:MyPack'.",
            context=ctx,
        )

    # Import module
    try:
        module = importlib.import_module(module_path)
    except Exception:
        ctx = ErrorContext().add("module", module_path).add("dotted_path", dotted_path)
        raise ImportError_(
            f"Module not found: '{module_path}'",
            why="The module specified in the pack path could not be imported.",
            fix="Check that the module exists and is on your Python path.",
            context=ctx,
        ) from None

    # Get symbol
    try:
        symbol = getattr(module, symbol_name)
    except AttributeError:
        ctx = (
            ErrorContext()
            .add("module", module_path)
            .add("symbol", symbol_name)
            .add("dotted_path", dotted_path)
        )
        raise ImportError_(
            f"Symbol '{symbol_name}' not found in module '{module_path}'",
            why="The module was imported but doesn't contain that symbol.",
            fix="Check the spelling of the pack class/instance name.",
            context=ctx,
        ) from None

    # Handle instance vs class
    if _is_statepack_instance(symbol):
        return symbol  # type: ignore

    if _is_statepack_class(symbol):
        try:
            instance = symbol()
            if _is_statepack_instance(instance):
                return instance
        except Exception as e:
            ctx = ErrorContext().add("dotted_path", dotted_path).add("error", str(e))
            raise ConfigError(
                f"Failed to instantiate pack: '{dotted_path}'",
                why=f"The pack class raised an error during instantiation: {e}",
                fix="Ensure the pack class has a zero-argument constructor.",
                context=ctx,
            ) from None

    # Not a StatePack
    ctx = (
        ErrorContext()
        .add("dotted_path", dotted_path)
        .add("got_type", type(symbol).__name__)
    )
    raise ConfigError(
        f"Not a StatePack: '{dotted_path}'",
        why=f"Expected a StatePack class or instance, got {type(symbol).__name__}.",
        fix="Ensure the symbol implements the StatePack protocol "
        "(name, provides, transitions, depends_on).",
        context=ctx,
    )


def _detect_collisions(
    packs: List[StatePack],
    builtin_keys: Set[str],
) -> List[ConfigError]:
    """Detect collisions between packs and with builtins.

    Returns a list of errors (empty if no collisions).
    """
    errors: List[ConfigError] = []

    # Track which pack provides each key
    key_providers: Dict[str, List[str]] = {}  # key -> [pack_names]

    for pack in packs:
        pack_name = pack.name
        for key in pack.provides().keys():
            if key not in key_providers:
                key_providers[key] = []
            key_providers[key].append(pack_name)

    # Check for duplicate keys across packs
    for key, providers in key_providers.items():
        if len(providers) > 1:
            ctx = ErrorContext().add("key", key).add("providers", providers)
            errors.append(
                ConfigError(
                    f"Duplicate state key: '{key}'",
                    why=f"Multiple packs provide the same state key: {', '.join(providers)}.",
                    fix="Rename the state in one of the packs to avoid collision.",
                    context=ctx,
                )
            )

    # Check for shadowing builtins
    for key in key_providers.keys():
        if key in builtin_keys:
            providers = key_providers[key]
            ctx = (
                ErrorContext()
                .add("key", key)
                .add("providers", providers)
                .add("builtin", True)
            )
            errors.append(
                ConfigError(
                    f"State key '{key}' shadows builtin",
                    why=f"Pack(s) {', '.join(providers)} provide a key that conflicts with a builtin state.",
                    fix=f"Rename '{key}' in the pack to avoid shadowing the builtin.",
                    context=ctx,
                )
            )

    return errors


def load_packs(
    *,
    states: Optional[Dict[str, type]] = None,
    packs: Optional[List[Union[StatePack, str]]] = None,
    builtin_keys: Optional[Set[str]] = None,
) -> List[StatePack]:
    """Load and validate StatePacks from various sources.

    Accepts either legacy `states:` mapping or new `packs:` list (not both).
    Detects collisions and raises structured errors.

    Args:
        states: Legacy states mapping {key: StateClass}. Wrapped in MappingPack.
        packs: List of StatePack instances or dotted paths to load.
        builtin_keys: Set of builtin state keys for collision detection.

    Returns:
        List of StatePack instances in deterministic order.

    Raises:
        ConfigError: If both states and packs are provided, or on collision.
        ImportError_: If a dotted path cannot be resolved.

    Example:
        # Legacy format
        packs = load_packs(states={"Idle": IdleState, "Active": ActiveState})

        # New format
        packs = load_packs(packs=["myapp.packs:SessionPack", "myapp.packs:CachePack"])

        # Programmatic
        packs = load_packs(packs=[SessionPack(), CachePack()])
    """
    if builtin_keys is None:
        builtin_keys = set()

    # Validate: can't have both states and packs
    if states is not None and packs is not None:
        ctx = ErrorContext().add("has_states", True).add("has_packs", True)
        raise ConfigError(
            "Cannot specify both 'states' and 'packs'",
            why="The legacy 'states:' mapping and new 'packs:' list are mutually exclusive. "
            "Both define state sources, creating ambiguity about which states to use.",
            fix="Remove one: keep 'states:' for simple configs, or migrate to 'packs:' "
            "by wrapping your states in a StatePack class.",
            context=ctx,
        )

    result: List[StatePack] = []

    # Handle legacy states mapping
    if states is not None:
        result.append(MappingPack(states))

    # Handle packs list
    if packs is not None:
        for item in packs:
            if isinstance(item, str):
                # Dotted path - load it
                pack = _load_pack_from_dotted_path(item)
                result.append(pack)
            elif _is_statepack_instance(item):
                # Already a StatePack instance
                result.append(item)  # type: ignore
            else:
                ctx = ErrorContext().add("item", str(item)).add("type", type(item).__name__)
                raise ConfigError(
                    f"Invalid pack entry: {item!r}",
                    why=f"Expected StatePack instance or dotted path string, got {type(item).__name__}.",
                    fix="Provide either a StatePack instance or a string like 'mypackage:PackClass'.",
                    context=ctx,
                )

    # Detect collisions
    collision_errors = _detect_collisions(result, builtin_keys)
    if collision_errors:
        # Raise the first error (all errors are in the list for potential future batch reporting)
        # For now, raise the first to match existing error behavior
        raise collision_errors[0]

    return result


def collect_provided_keys(packs: List[StatePack]) -> Dict[str, str]:
    """Collect all state keys provided by packs with attribution.

    Args:
        packs: List of StatePack instances.

    Returns:
        Dict mapping state key to pack name that provides it.
    """
    result: Dict[str, str] = {}
    for pack in packs:
        for key in pack.provides().keys():
            if key not in result:  # First provider wins (collision already detected)
                result[key] = pack.name
    return result
