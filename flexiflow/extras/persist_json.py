"""JSON file persistence adapter for FlexiFlow components."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


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
        ValueError: If JSON is invalid or missing required fields
    """
    p = Path(path)

    if not p.exists():
        raise FileNotFoundError(f"State file not found: {path}")

    try:
        with p.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in state file '{path}': {e}") from None

    # Validate required fields
    if not isinstance(data, dict):
        raise ValueError(f"State file must contain a JSON object, got {type(data).__name__}")

    name = data.get("name")
    if not name or not isinstance(name, str):
        raise ValueError("State file missing required field: 'name'")

    current_state = data.get("current_state")
    if not current_state or not isinstance(current_state, str):
        raise ValueError("State file missing required field: 'current_state'")

    rules = data.get("rules", [])
    if not isinstance(rules, list):
        raise ValueError("'rules' must be a list")

    metadata = data.get("metadata", {})
    if not isinstance(metadata, dict):
        raise ValueError("'metadata' must be a dict")

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
        ValueError: If the state class is not found in the registry
    """
    from ..component import AsyncComponent
    from ..state_machine import StateMachine, DEFAULT_REGISTRY

    reg = registry or DEFAULT_REGISTRY

    # Validate state exists in registry
    if snapshot.current_state not in reg.names():
        raise ValueError(
            f"Cannot restore: state '{snapshot.current_state}' not found in registry. "
            f"Available states: {list(reg.names())}"
        )

    component = AsyncComponent(
        name=snapshot.name,
        rules=list(snapshot.rules),
        state_machine=StateMachine.from_name(snapshot.current_state, registry=reg),
    )

    engine.register(component)
    return component
