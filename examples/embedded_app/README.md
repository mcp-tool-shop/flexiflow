# Embedded App Example

A complete example showing FlexiFlow embedded in an application with:

- Custom states (state packs via `states:` mapping)
- SQLite persistence with automatic snapshots
- Observability event subscriptions
- Retention management with pruning

## Files

| File | Purpose |
|------|---------|
| `config.yaml` | Component config with state pack |
| `states.py` | Custom state classes |
| `app.py` | Main application |
| `state.db` | SQLite database (created on first run) |

## Run

```bash
cd examples/embedded_app
python app.py
```

## What It Does

1. Loads config with custom states registered via `states:` mapping
2. Checks SQLite for existing snapshot; restores if found
3. Subscribes to `state.changed` events for observability
4. On each state change: saves snapshot, prunes old entries
5. Runs a demo workflow showing state transitions
6. Prints snapshot history

## Output

```
Restored from snapshot: Complete
--- or ---
Starting fresh: Idle

--- Running job workflow demo ---

Current state: Idle
Sending: start_job
  [job_processor] Idle -> Processing
Sending: complete
  [job_processor] Processing -> Complete
...

Final state: Complete

--- Snapshot History (last 5) ---
  7: Complete at 2024-01-28T12:00:00+00:00
  6: Processing at 2024-01-28T11:59:59+00:00
  ...
```

## Key Patterns

### State Packs in Config

```yaml
states:
  Idle: "states:Idle"
  Processing: "states:Processing"
initial_state: Idle
```

### Restore or Create

```python
snapshot = load_latest_snapshot_sqlite(conn, config.name)
if snapshot:
    component = AsyncComponent(
        name=snapshot.name,
        state_machine=StateMachine.from_name(snapshot.current_state),
    )
else:
    component = AsyncComponent(
        name=config.name,
        state_machine=StateMachine.from_name(config.initial_state),
    )
```

### Save on State Change

```python
async def on_state_changed(data):
    snapshot = ComponentSnapshot(
        name=data["component"],
        current_state=data["to_state"],
        rules=component.rules,
        metadata={},
    )
    save_snapshot_sqlite(conn, snapshot)
    prune_snapshots_sqlite(conn, data["component"], keep_last=50)

await engine.event_bus.subscribe("state.changed", "observer", on_state_changed)
```
