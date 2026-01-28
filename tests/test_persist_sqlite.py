"""Tests for SQLite persistence adapter."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

import pytest

from flexiflow import PersistenceError
from flexiflow.extras.persist_json import ComponentSnapshot
from flexiflow.extras.persist_sqlite import (
    list_snapshots,
    load_latest_snapshot,
    prune_snapshots,
    save_snapshot,
)


@pytest.fixture
def conn():
    """In-memory SQLite connection for testing."""
    connection = sqlite3.connect(":memory:")
    yield connection
    connection.close()


def test_roundtrip_save_load(conn: sqlite3.Connection):
    """Save and load preserves snapshot data."""
    snapshot = ComponentSnapshot(
        name="test_comp",
        current_state="AwaitingConfirmation",
        rules=[{"rule1": "value1"}],
        metadata={"version": "1.0"},
    )

    row_id = save_snapshot(conn, snapshot)
    assert row_id >= 1

    loaded = load_latest_snapshot(conn, "test_comp")
    assert loaded is not None
    assert loaded.name == "test_comp"
    assert loaded.current_state == "AwaitingConfirmation"
    assert loaded.rules == [{"rule1": "value1"}]
    assert loaded.metadata == {"version": "1.0"}


def test_load_missing_returns_none(conn: sqlite3.Connection):
    """load_latest_snapshot returns None for unknown component."""
    result = load_latest_snapshot(conn, "nonexistent")
    assert result is None


def test_load_latest_returns_most_recent(conn: sqlite3.Connection):
    """load_latest_snapshot returns the most recent snapshot."""
    # Save older snapshot
    old_snapshot = ComponentSnapshot(
        name="versioned",
        current_state="InitialState",
        rules=[],
        metadata={},
    )
    save_snapshot(
        conn,
        old_snapshot,
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )

    # Save newer snapshot
    new_snapshot = ComponentSnapshot(
        name="versioned",
        current_state="CompleteState",
        rules=[{"new": True}],
        metadata={"updated": True},
    )
    save_snapshot(
        conn,
        new_snapshot,
        created_at=datetime(2024, 6, 1, tzinfo=timezone.utc),
    )

    loaded = load_latest_snapshot(conn, "versioned")
    assert loaded is not None
    assert loaded.current_state == "CompleteState"
    assert loaded.rules == [{"new": True}]


def test_list_snapshots_returns_history(conn: sqlite3.Connection):
    """list_snapshots returns snapshot history in reverse chronological order."""
    for i in range(5):
        snapshot = ComponentSnapshot(
            name="history_comp",
            current_state=f"State{i}",
            rules=[],
            metadata={},
        )
        save_snapshot(
            conn,
            snapshot,
            created_at=datetime(2024, 1, i + 1, tzinfo=timezone.utc),
        )

    history = list_snapshots(conn, "history_comp", limit=3)
    assert len(history) == 3

    # Most recent first
    assert history[0]["current_state"] == "State4"
    assert history[1]["current_state"] == "State3"
    assert history[2]["current_state"] == "State2"

    # Each entry has expected keys
    for entry in history:
        assert "id" in entry
        assert "created_at" in entry
        assert "current_state" in entry


def test_list_snapshots_empty_returns_empty(conn: sqlite3.Connection):
    """list_snapshots returns empty list for unknown component."""
    result = list_snapshots(conn, "nonexistent")
    assert result == []


def test_invalid_json_raises_valueerror(conn: sqlite3.Connection):
    """load_latest_snapshot raises ValueError for corrupt JSON."""
    # Manually insert invalid JSON into the namespaced table
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS flexiflow_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            component_name TEXT NOT NULL,
            snapshot_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        INSERT INTO flexiflow_snapshots (component_name, snapshot_json, created_at)
        VALUES (?, ?, ?)
        """,
        ("corrupt", "not valid json {{{", datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()

    with pytest.raises(PersistenceError, match="Invalid JSON"):
        load_latest_snapshot(conn, "corrupt")


def test_multiple_components_isolated(conn: sqlite3.Connection):
    """Snapshots for different components don't interfere."""
    snap_a = ComponentSnapshot(
        name="comp_a",
        current_state="StateA",
        rules=[],
        metadata={},
    )
    snap_b = ComponentSnapshot(
        name="comp_b",
        current_state="StateB",
        rules=[],
        metadata={},
    )

    save_snapshot(conn, snap_a)
    save_snapshot(conn, snap_b)

    loaded_a = load_latest_snapshot(conn, "comp_a")
    loaded_b = load_latest_snapshot(conn, "comp_b")

    assert loaded_a is not None
    assert loaded_a.current_state == "StateA"
    assert loaded_b is not None
    assert loaded_b.current_state == "StateB"


def test_save_returns_incrementing_ids(conn: sqlite3.Connection):
    """save_snapshot returns incrementing row IDs."""
    snapshot = ComponentSnapshot(
        name="test",
        current_state="InitialState",
        rules=[],
        metadata={},
    )

    id1 = save_snapshot(conn, snapshot)
    id2 = save_snapshot(conn, snapshot)
    id3 = save_snapshot(conn, snapshot)

    assert id2 == id1 + 1
    assert id3 == id2 + 1


def test_prune_snapshots_keeps_recent(conn: sqlite3.Connection):
    """prune_snapshots keeps the most recent N and deletes older ones."""
    # Create 10 snapshots
    for i in range(10):
        snapshot = ComponentSnapshot(
            name="prunable",
            current_state=f"State{i}",
            rules=[],
            metadata={},
        )
        save_snapshot(
            conn,
            snapshot,
            created_at=datetime(2024, 1, i + 1, tzinfo=timezone.utc),
        )

    # Verify all 10 exist
    history = list_snapshots(conn, "prunable", limit=20)
    assert len(history) == 10

    # Prune to keep last 3
    deleted = prune_snapshots(conn, "prunable", keep_last=3)
    assert deleted == 7

    # Verify only 3 remain (most recent)
    history = list_snapshots(conn, "prunable", limit=20)
    assert len(history) == 3
    assert history[0]["current_state"] == "State9"
    assert history[1]["current_state"] == "State8"
    assert history[2]["current_state"] == "State7"


def test_prune_snapshots_noop_when_few(conn: sqlite3.Connection):
    """prune_snapshots does nothing if fewer than keep_last exist."""
    # Create 2 snapshots
    for i in range(2):
        snapshot = ComponentSnapshot(
            name="small",
            current_state=f"State{i}",
            rules=[],
            metadata={},
        )
        save_snapshot(conn, snapshot)

    # Try to prune keeping 5 (more than exist)
    deleted = prune_snapshots(conn, "small", keep_last=5)
    assert deleted == 0

    # Both still exist
    history = list_snapshots(conn, "small", limit=10)
    assert len(history) == 2


def test_prune_snapshots_isolates_components(conn: sqlite3.Connection):
    """prune_snapshots only affects the specified component."""
    # Create snapshots for two components
    for i in range(5):
        snap_a = ComponentSnapshot(name="comp_a", current_state=f"A{i}", rules=[], metadata={})
        snap_b = ComponentSnapshot(name="comp_b", current_state=f"B{i}", rules=[], metadata={})
        save_snapshot(conn, snap_a, created_at=datetime(2024, 1, i + 1, tzinfo=timezone.utc))
        save_snapshot(conn, snap_b, created_at=datetime(2024, 1, i + 1, tzinfo=timezone.utc))

    # Prune only comp_a
    deleted = prune_snapshots(conn, "comp_a", keep_last=2)
    assert deleted == 3

    # comp_a has 2, comp_b still has 5
    assert len(list_snapshots(conn, "comp_a", limit=10)) == 2
    assert len(list_snapshots(conn, "comp_b", limit=10)) == 5
