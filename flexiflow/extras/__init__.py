"""Optional extras for FlexiFlow."""

from .retry import retry_async, RetryConfig
from .persist_json import (
    save_component,
    load_snapshot,
    restore_component,
    ComponentSnapshot,
)
from .persist_sqlite import (
    save_snapshot as save_snapshot_sqlite,
    load_latest_snapshot as load_latest_snapshot_sqlite,
    list_snapshots as list_snapshots_sqlite,
    prune_snapshots as prune_snapshots_sqlite,
)

__all__ = [
    # Retry
    "retry_async",
    "RetryConfig",
    # JSON persistence
    "save_component",
    "load_snapshot",
    "restore_component",
    "ComponentSnapshot",
    # SQLite persistence
    "save_snapshot_sqlite",
    "load_latest_snapshot_sqlite",
    "list_snapshots_sqlite",
    "prune_snapshots_sqlite",
]
