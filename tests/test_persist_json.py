"""Tests for JSON persistence adapter."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from flexiflow import PersistenceError, StateError
from flexiflow.component import AsyncComponent
from flexiflow.engine import FlexiFlowEngine
from flexiflow.extras.persist_json import (
    ComponentSnapshot,
    load_snapshot,
    restore_component,
    save_component,
)
from flexiflow.state_machine import StateMachine


async def test_roundtrip_save_load(tmp_path: Path):
    """Save and load preserves component state."""
    state_file = tmp_path / "state.json"

    # Create component and transition to a non-initial state
    component = AsyncComponent(
        name="test_comp",
        rules=[{"rule1": "value1"}],
        state_machine=StateMachine.from_name("InitialState"),
    )
    await component.state_machine.handle_message({"type": "start"}, component)
    assert component.state_machine.current_state.__class__.__name__ == "AwaitingConfirmation"

    # Save with metadata
    save_component(component, state_file, metadata={"version": "1.0"})

    # Load snapshot
    snapshot = load_snapshot(state_file)

    assert snapshot.name == "test_comp"
    assert snapshot.current_state == "AwaitingConfirmation"
    assert snapshot.rules == [{"rule1": "value1"}]
    assert snapshot.metadata == {"version": "1.0"}


async def test_restore_component_registers_with_engine(tmp_path: Path):
    """restore_component creates and registers component with engine."""
    state_file = tmp_path / "state.json"

    # Create and save a component
    original = AsyncComponent(
        name="restorable",
        rules=[{"r": 1}],
        state_machine=StateMachine.from_name("InitialState"),
    )
    await original.state_machine.handle_message({"type": "start"}, original)
    save_component(original, state_file)

    # Restore into a new engine
    engine = FlexiFlowEngine()
    snapshot = load_snapshot(state_file)
    restored = restore_component(snapshot, engine)

    assert engine.get("restorable") is restored
    assert restored.name == "restorable"
    assert restored.rules == [{"r": 1}]
    assert restored.state_machine.current_state.__class__.__name__ == "AwaitingConfirmation"


def test_load_file_not_found(tmp_path: Path):
    """load_snapshot raises FileNotFoundError for missing file."""
    with pytest.raises(FileNotFoundError, match="State file not found"):
        load_snapshot(tmp_path / "nonexistent.json")


def test_load_invalid_json(tmp_path: Path):
    """load_snapshot raises PersistenceError for invalid JSON."""
    state_file = tmp_path / "bad.json"
    state_file.write_text("not valid json {", encoding="utf-8")

    with pytest.raises(PersistenceError, match="Invalid JSON"):
        load_snapshot(state_file)


def test_load_missing_required_fields(tmp_path: Path):
    """load_snapshot raises PersistenceError for missing required fields."""
    state_file = tmp_path / "incomplete.json"

    # Missing 'name'
    state_file.write_text('{"current_state": "InitialState"}', encoding="utf-8")
    with pytest.raises(PersistenceError, match="missing"):
        load_snapshot(state_file)

    # Missing 'current_state'
    state_file.write_text('{"name": "test"}', encoding="utf-8")
    with pytest.raises(PersistenceError, match="missing"):
        load_snapshot(state_file)


def test_restore_unknown_state_errors(tmp_path: Path):
    """restore_component raises StateError for unknown state."""
    state_file = tmp_path / "unknown_state.json"
    state_file.write_text(
        json.dumps({
            "name": "test",
            "current_state": "NonExistentState",
            "rules": [],
            "metadata": {},
        }),
        encoding="utf-8",
    )

    snapshot = load_snapshot(state_file)
    engine = FlexiFlowEngine()

    with pytest.raises(StateError, match="Unknown state"):
        restore_component(snapshot, engine)


def test_save_creates_parent_directories(tmp_path: Path):
    """save_component creates parent directories if needed."""
    state_file = tmp_path / "nested" / "dirs" / "state.json"

    component = AsyncComponent(
        name="test",
        state_machine=StateMachine.from_name("InitialState"),
    )
    save_component(component, state_file)

    assert state_file.exists()
    snapshot = load_snapshot(state_file)
    assert snapshot.name == "test"
