"""JSON file persistence adapter for FlexiFlow components."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..errors import (
    ErrorContext,
    PersistenceError,
    persistence_invalid_json,
    persistence_missing_field,
    state_not_found,
)


@dataclass(frozen=True)
class ComponentSnapshot:
    """Serializable snapshot of component state."""

    name: str
    current_state: str
    rules: List[dict]
    metadata: Dict[str, Any]


def save_component(
    component: Any,
    path: str | Path,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Save component state to a JSON file.

    Args:
        component: An AsyncComponent instance
        path: Path to the JSON file
        metadata: Optional user-defined metadata to persist

    Raises:
        IOError: If file cannot be written
    """
    snapshot = {
        "name": component.name,
        "current_state": component.state_machine.current_state.__class__.__name__,
        "rules": component.rules,
        "metadata": metadata or {},
    }

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    with p.open("w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2)


def load_snapshot(path: str | Path) -> ComponentSnapshot:
    """
    Load a component snapshot from a JSON file.

    Args:
        path: Path to the JSON file

    Returns:
        ComponentSnapshot with persisted data

    Raises:
        FileNotFoundError: If file doesn't exist
        PersistenceError: If JSON is invalid or missing required fields
    """
    p = Path(path)
    path_str = str(path)

    if not p.exists():
        raise FileNotFoundError(f"State file not found: {path}")

    try:
        with p.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise persistence_invalid_json(path_str, str(e)) from None

    # Validate required fields
    if not isinstance(data, dict):
        ctx = ErrorContext()
        ctx.add("path", path_str)
        ctx.add("got_type", type(data).__name__)
        raise PersistenceError(
            "State file must contain a JSON object",
            why=f"Expected a JSON object, but got {type(data).__name__}.",
            fix="Ensure the file contains a JSON object with 'name' and 'current_state' fields.",
            context=ctx,
        )

    name = data.get("name")
    if not name or not isinstance(name, str):
        raise persistence_missing_field(path_str, "name")

    current_state = data.get("current_state")
    if not current_state or not isinstance(current_state, str):
        raise persistence_missing_field(path_str, "current_state")

    rules = data.get("rules", [])
    if not isinstance(rules, list):
        ctx = ErrorContext()
        ctx.add("path", path_str)
        ctx.add("got_type", type(rules).__name__)
        raise PersistenceError(
            "State file 'rules' field has wrong type",
            why=f"Expected a list, but got {type(rules).__name__}.",
            fix="Change 'rules' to be a list, or remove it to use default.",
            context=ctx,
        )

    metadata = data.get("metadata", {})
    if not isinstance(metadata, dict):
        ctx = ErrorContext()
        ctx.add("path", path_str)
        ctx.add("got_type", type(metadata).__name__)
        raise PersistenceError(
            "State file 'metadata' field has wrong type",
            why=f"Expected a dict, but got {type(metadata).__name__}.",
            fix="Change 'metadata' to be a dict, or remove it to use default.",
            context=ctx,
        )

    return ComponentSnapshot(
        name=name,
        current_state=current_state,
        rules=rules,
        metadata=metadata,
    )


def restore_component(
    snapshot: ComponentSnapshot,
    engine: Any,
    registry: Optional[Any] = None,
) -> Any:
    """
    Restore a component from a snapshot and register it with an engine.

    Args:
        snapshot: ComponentSnapshot to restore from
        engine: FlexiFlowEngine to register with
        registry: Optional StateRegistry (uses DEFAULT_REGISTRY if not provided)

    Returns:
        The restored AsyncComponent

    Raises:
        StateError: If the state class is not found in the registry
    """
    from ..component import AsyncComponent
    from ..state_machine import DEFAULT_REGISTRY, StateMachine

    reg = registry or DEFAULT_REGISTRY

    # Validate state exists in registry
    if snapshot.current_state not in reg.names():
        raise state_not_found(snapshot.current_state, reg.names())

    component = AsyncComponent(
        name=snapshot.name,
        rules=list(snapshot.rules),
        state_machine=StateMachine.from_name(snapshot.current_state, registry=reg),
    )

    engine.register(component)
    return component
