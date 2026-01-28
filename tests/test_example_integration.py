"""Integration tests for the embedded_app example.

These tests verify that the example in examples/embedded_app/ works correctly
and that the documented patterns don't regress.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

# Add the example directory to path so we can import its modules
EXAMPLE_DIR = Path(__file__).parent.parent / "examples" / "embedded_app"
sys.path.insert(0, str(EXAMPLE_DIR))


@pytest.fixture
def example_conn(tmp_path):
    """In-memory SQLite connection for testing."""
    conn = sqlite3.connect(":memory:")
    yield conn
    conn.close()


@pytest.fixture
def example_config():
    """Load the example config, registering custom states."""
    from flexiflow.config_loader import ConfigLoader

    config_path = EXAMPLE_DIR / "config.yaml"
    return ConfigLoader.load_component_config(config_path)


def test_example_states_importable():
    """Example custom states are importable."""
    from states import Complete, Failed, Idle, Processing

    assert Idle.__name__ == "Idle"
    assert Processing.__name__ == "Processing"
    assert Complete.__name__ == "Complete"
    assert Failed.__name__ == "Failed"


def test_example_config_loads(example_config):
    """Example config loads and registers custom states."""
    assert example_config.name == "job_processor"
    assert example_config.initial_state == "Idle"

    # Verify custom states are registered
    from flexiflow.state_machine import DEFAULT_REGISTRY

    assert "Idle" in DEFAULT_REGISTRY.names()
    assert "Processing" in DEFAULT_REGISTRY.names()
    assert "Complete" in DEFAULT_REGISTRY.names()
    assert "Failed" in DEFAULT_REGISTRY.names()


@pytest.mark.asyncio
async def test_example_workflow_happy_path(example_config, example_conn):
    """Example workflow runs: Idle -> Processing -> Complete."""
    from flexiflow.component import AsyncComponent
    from flexiflow.engine import FlexiFlowEngine
    from flexiflow.extras import (
        ComponentSnapshot,
        list_snapshots_sqlite,
        load_latest_snapshot_sqlite,
        save_snapshot_sqlite,
    )
    from flexiflow.state_machine import StateMachine

    # Create engine and component
    engine = FlexiFlowEngine()
    component = AsyncComponent(
        name=example_config.name,
        rules=list(example_config.rules),
        state_machine=StateMachine.from_name(example_config.initial_state),
    )
    engine.register(component)

    # Track state changes
    transitions = []

    async def on_state_changed(data):
        transitions.append((data["from_state"], data["to_state"]))
        # Save snapshot (mimics example behavior)
        snapshot = ComponentSnapshot(
            name=data["component"],
            current_state=data["to_state"],
            rules=component.rules,
            metadata={},
        )
        save_snapshot_sqlite(example_conn, snapshot)

    await engine.event_bus.subscribe("state.changed", "test", on_state_changed)

    # Run workflow
    assert component.state_machine.current_state.__class__.__name__ == "Idle"

    await component.handle_message({"type": "start_job"})
    assert component.state_machine.current_state.__class__.__name__ == "Processing"

    await component.handle_message({"type": "complete"})
    assert component.state_machine.current_state.__class__.__name__ == "Complete"

    # Verify transitions recorded
    assert transitions == [("Idle", "Processing"), ("Processing", "Complete")]

    # Verify snapshots persisted
    history = list_snapshots_sqlite(example_conn, example_config.name, limit=10)
    assert len(history) == 2
    assert history[0]["current_state"] == "Complete"
    assert history[1]["current_state"] == "Processing"

    # Verify restore works
    latest = load_latest_snapshot_sqlite(example_conn, example_config.name)
    assert latest is not None
    assert latest.current_state == "Complete"


@pytest.mark.asyncio
async def test_example_workflow_failure_retry(example_config, example_conn):
    """Example workflow handles failure and retry: Idle -> Processing -> Failed -> Processing -> Complete."""
    from flexiflow.component import AsyncComponent
    from flexiflow.engine import FlexiFlowEngine
    from flexiflow.state_machine import StateMachine

    engine = FlexiFlowEngine()
    component = AsyncComponent(
        name=example_config.name,
        rules=list(example_config.rules),
        state_machine=StateMachine.from_name(example_config.initial_state),
    )
    engine.register(component)

    # Start job
    await component.handle_message({"type": "start_job"})
    assert component.state_machine.current_state.__class__.__name__ == "Processing"

    # Fail
    await component.handle_message({"type": "fail"})
    assert component.state_machine.current_state.__class__.__name__ == "Failed"

    # Retry
    await component.handle_message({"type": "retry"})
    assert component.state_machine.current_state.__class__.__name__ == "Processing"

    # Complete
    await component.handle_message({"type": "complete"})
    assert component.state_machine.current_state.__class__.__name__ == "Complete"


@pytest.mark.asyncio
async def test_example_restore_from_snapshot(example_config, example_conn):
    """Component can be restored from a saved snapshot."""
    from flexiflow.component import AsyncComponent
    from flexiflow.engine import FlexiFlowEngine
    from flexiflow.extras import (
        ComponentSnapshot,
        load_latest_snapshot_sqlite,
        save_snapshot_sqlite,
    )
    from flexiflow.state_machine import StateMachine

    # Save a snapshot as if previous session ended in Processing
    snapshot = ComponentSnapshot(
        name=example_config.name,
        current_state="Processing",
        rules=list(example_config.rules),
        metadata={"session": "previous"},
    )
    save_snapshot_sqlite(example_conn, snapshot)

    # Load snapshot and restore
    loaded = load_latest_snapshot_sqlite(example_conn, example_config.name)
    assert loaded is not None

    engine = FlexiFlowEngine()
    component = AsyncComponent(
        name=loaded.name,
        rules=list(loaded.rules),
        state_machine=StateMachine.from_name(loaded.current_state),
    )
    engine.register(component)

    # Verify restored state
    assert component.state_machine.current_state.__class__.__name__ == "Processing"

    # Can continue from restored state
    await component.handle_message({"type": "complete"})
    assert component.state_machine.current_state.__class__.__name__ == "Complete"
