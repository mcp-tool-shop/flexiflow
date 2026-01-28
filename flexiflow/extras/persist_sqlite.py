"""SQLite persistence adapter for FlexiFlow components.

This adapter stores every snapshot indefinitely. Callers should implement
retention/cleanup if storage growth is a concern. Use prune_snapshots() to
delete old snapshots while keeping the most recent N per component.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import List, Optional

from .persist_json import ComponentSnapshot


def _ensure_table(conn: sqlite3.Connection) -> None:
    """Create the snapshots table if it doesn't exist."""
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
        CREATE INDEX IF NOT EXISTS idx_flexiflow_snapshots_component_created
        ON flexiflow_snapshots (component_name, created_at DESC)
        """
    )


def save_snapshot(
    conn: sqlite3.Connection,
    snapshot: ComponentSnapshot,
    *,
    created_at: Optional[datetime] = None,
) -> int:
    """
    Save a component snapshot to SQLite.

    Args:
        conn: SQLite connection
        snapshot: ComponentSnapshot to persist
        created_at: Optional timestamp (defaults to now UTC)

    Returns:
        The row ID of the inserted snapshot
    """
    _ensure_table(conn)

    timestamp = created_at or datetime.now(timezone.utc)
    payload = json.dumps(
        {
            "name": snapshot.name,
            "current_state": snapshot.current_state,
            "rules": snapshot.rules,
            "metadata": snapshot.metadata,
        }
    )

    cursor = conn.execute(
        """
        INSERT INTO flexiflow_snapshots (component_name, snapshot_json, created_at)
        VALUES (?, ?, ?)
        """,
        (snapshot.name, payload, timestamp.isoformat()),
    )
    conn.commit()
    return cursor.lastrowid  # type: ignore[return-value]


def load_latest_snapshot(
    conn: sqlite3.Connection,
    component_name: str,
) -> Optional[ComponentSnapshot]:
    """
    Load the most recent snapshot for a component.

    Args:
        conn: SQLite connection
        component_name: Name of the component to load

    Returns:
        ComponentSnapshot if found, None otherwise

    Raises:
        ValueError: If the stored JSON is invalid
    """
    _ensure_table(conn)

    cursor = conn.execute(
        """
        SELECT snapshot_json FROM flexiflow_snapshots
        WHERE component_name = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (component_name,),
    )
    row = cursor.fetchone()

    if row is None:
        return None

    try:
        data = json.loads(row[0])
    except json.JSONDecodeError as e:
        from ..errors import ErrorContext, PersistenceError

        ctx = ErrorContext()
        ctx.add("component_name", component_name)
        ctx.add("error", str(e))
        raise PersistenceError(
            f"Invalid JSON in snapshot for '{component_name}'",
            why="The database contains a snapshot with malformed JSON.",
            fix="Delete the corrupted row from flexiflow_snapshots table, "
            "or use prune_snapshots to clean up old entries.",
            context=ctx,
        ) from None

    return ComponentSnapshot(
        name=data["name"],
        current_state=data["current_state"],
        rules=data.get("rules", []),
        metadata=data.get("metadata", {}),
    )


def list_snapshots(
    conn: sqlite3.Connection,
    component_name: str,
    *,
    limit: int = 10,
) -> List[dict]:
    """
    List recent snapshots for a component.

    Args:
        conn: SQLite connection
        component_name: Name of the component
        limit: Maximum number of snapshots to return (default 10)

    Returns:
        List of dicts with 'id', 'created_at', and 'current_state' keys
    """
    _ensure_table(conn)

    cursor = conn.execute(
        """
        SELECT id, snapshot_json, created_at FROM flexiflow_snapshots
        WHERE component_name = ?
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (component_name, limit),
    )

    results = []
    for row in cursor:
        try:
            data = json.loads(row[1])
            current_state = data.get("current_state", "unknown")
        except json.JSONDecodeError:
            current_state = "invalid"

        results.append(
            {
                "id": row[0],
                "created_at": row[2],
                "current_state": current_state,
            }
        )

    return results


def prune_snapshots(
    conn: sqlite3.Connection,
    component_name: str,
    *,
    keep_last: int = 10,
) -> int:
    """
    Delete old snapshots, keeping only the most recent N.

    Args:
        conn: SQLite connection
        component_name: Name of the component to prune
        keep_last: Number of most recent snapshots to keep (default 10)

    Returns:
        Number of rows deleted
    """
    _ensure_table(conn)

    # Find the cutoff ID (the Nth most recent)
    cursor = conn.execute(
        """
        SELECT id FROM flexiflow_snapshots
        WHERE component_name = ?
        ORDER BY created_at DESC
        LIMIT 1 OFFSET ?
        """,
        (component_name, keep_last),
    )
    cutoff_row = cursor.fetchone()

    if cutoff_row is None:
        # Fewer than keep_last snapshots exist, nothing to prune
        return 0

    cutoff_id = cutoff_row[0]

    # Delete all rows older than or equal to the cutoff
    cursor = conn.execute(
        """
        DELETE FROM flexiflow_snapshots
        WHERE component_name = ? AND id <= ?
        """,
        (component_name, cutoff_id),
    )
    conn.commit()
    return cursor.rowcount
