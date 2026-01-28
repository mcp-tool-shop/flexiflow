#!/usr/bin/env python
"""
Embedded FlexiFlow Application Example

Demonstrates:
- Loading config with custom states (state packs)
- Subscribing to observability events
- Restoring from SQLite if previous state exists
- Saving snapshots on state changes
- Periodic pruning for retention

Run: python app.py
"""

from __future__ import annotations

import asyncio
import sqlite3
import sys
from pathlib import Path

# Add the example directory to path so config can find states module
sys.path.insert(0, str(Path(__file__).parent))

from flexiflow.component import AsyncComponent
from flexiflow.config_loader import ConfigLoader
from flexiflow.engine import FlexiFlowEngine
from flexiflow.extras import (
    ComponentSnapshot,
    load_latest_snapshot_sqlite,
    prune_snapshots_sqlite,
    save_snapshot_sqlite,
)
from flexiflow.state_machine import StateMachine


async def main():
    # --- Setup ---
    config_path = Path(__file__).parent / "config.yaml"
    db_path = Path(__file__).parent / "state.db"

    # Load config (registers all custom states from states: mapping)
    config = ConfigLoader.load_component_config(config_path)

    # Connect to SQLite
    conn = sqlite3.connect(db_path)

    # Create engine
    engine = FlexiFlowEngine()

    # --- Restore or Create Component ---
    snapshot = load_latest_snapshot_sqlite(conn, config.name)

    if snapshot:
        print(f"Restored from snapshot: {snapshot.current_state}")
        component = AsyncComponent(
            name=snapshot.name,
            rules=list(snapshot.rules),
            state_machine=StateMachine.from_name(snapshot.current_state),
        )
    else:
        print(f"Starting fresh: {config.initial_state}")
        component = AsyncComponent(
            name=config.name,
            rules=list(config.rules),
            state_machine=StateMachine.from_name(config.initial_state),
        )

    engine.register(component)

    # --- Observability: Log State Changes ---
    async def on_state_changed(data):
        print(f"  [{data['component']}] {data['from_state']} -> {data['to_state']}")

        # Save snapshot on every state change
        snapshot = ComponentSnapshot(
            name=data["component"],
            current_state=data["to_state"],
            rules=component.rules,
            metadata={"triggered_by": "state_change"},
        )
        save_snapshot_sqlite(conn, snapshot)

        # Prune old snapshots (keep last 50)
        prune_snapshots_sqlite(conn, data["component"], keep_last=50)

    await engine.event_bus.subscribe(
        "state.changed", "observer", on_state_changed, priority=5
    )

    # --- Demo: Simulate a Job Workflow ---
    print("\n--- Running job workflow demo ---\n")

    print("Current state:", component.state_machine.current_state.__class__.__name__)

    # Start a job
    print("\nSending: start_job")
    await component.handle_message({"type": "start_job"})

    # Complete it
    print("Sending: complete")
    await component.handle_message({"type": "complete"})

    # Reset to idle
    print("Sending: reset")
    await component.handle_message({"type": "reset"})

    # Start another job that fails
    print("Sending: start_job")
    await component.handle_message({"type": "start_job"})

    print("Sending: fail")
    await component.handle_message({"type": "fail"})

    # Retry
    print("Sending: retry")
    await component.handle_message({"type": "retry"})

    # Complete
    print("Sending: complete")
    await component.handle_message({"type": "complete"})

    print(f"\nFinal state: {component.state_machine.current_state.__class__.__name__}")

    # --- Show History ---
    from flexiflow.extras import list_snapshots_sqlite

    print("\n--- Snapshot History (last 5) ---")
    history = list_snapshots_sqlite(conn, config.name, limit=5)
    for entry in history:
        print(f"  {entry['id']}: {entry['current_state']} at {entry['created_at']}")

    conn.close()
    print("\nDone. State persisted to state.db")


if __name__ == "__main__":
    asyncio.run(main())
