# FlexiFlow

FlexiFlow is a small, library-first async engine that wires:

- Components (rules + state machine)
- An async event bus (pub/sub with priority, filters, and sequential/concurrent delivery)
- Structured logging with correlation IDs
- A minimal CLI for demos

## Install

Editable install:

```bash
pip install -e .
```

Dev dependencies (tests):

```bash
pip install -e ".[dev]"
```

Optional hot reload:

```bash
pip install -e ".[reload]"
```

Optional API:

```bash
pip install -e ".[api]"
```

## Quickstart

```bash
flexiflow register --config examples/config.yaml --start
flexiflow handle --config examples/config.yaml confirm --content confirmed
flexiflow handle --config examples/config.yaml complete
flexiflow update_rules --config examples/config.yaml examples/new_rules.yaml
```

## Environment variable config

If you omit `--config`, FlexiFlow will use:

- `FLEXIFLOW_CONFIG=/path/to/config.yaml`

Example:

```bash
set FLEXIFLOW_CONFIG=examples/config.yaml
flexiflow register --start
```

## Message types in the default state machine

- start
- confirm (requires content == "confirmed")
- cancel
- complete
- error
- acknowledge

## Events

FlexiFlow uses an async pub/sub event bus with priorities, optional filters, and two delivery modes.

### Subscribing

`subscribe()` registers a handler and returns a `SubscriptionHandle` you can use for cleanup.

```python
handle = await bus.subscribe("my.event", "my_component", handler, priority=2)
```

- **Priorities**: `1` (highest) .. `5` (lowest, default=3)
- **Optional filter**: `filter_fn(event_name, data) -> bool` gates whether a handler runs

### Unsubscribing

For long-running processes, unsubscribe to avoid leaks:

```python
bus.unsubscribe(handle)        # returns True if removed
bus.unsubscribe_all("my_component")  # returns count removed
```

### Publishing

```python
await bus.publish("my.event", data, delivery="sequential", on_error="continue")
```

#### Delivery modes

| Mode | Behavior |
|------|----------|
| **sequential** (default) | Handlers run in priority order (1→5). Each awaited before the next. |
| **concurrent** | All handlers scheduled concurrently. Priority affects launch order, not completion. |

#### Error policy

| Policy | Behavior |
|--------|----------|
| **continue** (default) | Logs exceptions and proceeds to remaining handlers |
| **raise** | Raises immediately on first exception |

### Notes

- If an event has no subscribers, publishing is a no-op.
- In concurrent mode, completion order is non-deterministic by design.

## Retry Decorator

For handlers that need retry logic, use the optional decorator:

```python
from flexiflow.extras.retry import retry_async, RetryConfig

@retry_async(RetryConfig(max_attempts=3, base_delay=0.2, jitter=0.2))
async def my_handler(data):
    # will retry up to 3 times with exponential backoff
    ...
```

This keeps retry policy out of the engine and at the handler boundary where it belongs.

## Observability

FlexiFlow emits structured events for observability. Subscribe to these to build monitoring, metrics, or debugging tools.

| Event | When | Payload |
|-------|------|---------|
| `engine.component.registered` | Component registered with engine | `{component}` |
| `component.message.received` | Message received by component | `{component, message}` |
| `state.changed` | State machine transition | `{component, from_state, to_state}` |
| `event.handler.failed` | Handler raised exception (continue mode) | `{event_name, component_name, exception}` |

### Example: Logging all state changes

```python
async def log_transitions(data):
    print(f"{data['component']}: {data['from_state']} → {data['to_state']}")

await bus.subscribe("state.changed", "logger", log_transitions)
```

### Design notes

- Observability events are **fire-and-forget** — they never block core execution
- `event.handler.failed` does **not** fire recursively (handlers for this event that fail are swallowed)
- These events are separate from logging — use both as needed

## Custom States

Load custom state classes via dotted paths:

```yaml
initial_state: "mypkg.states:MyInitialState"
```

The class must be a `State` subclass. It will be auto-registered under its class name.

### State Packs

For components that need multiple custom states, use the `states:` mapping to register them all up-front:

```yaml
name: my_component
states:
  InitialState: "mypkg.states:InitialState"
  Processing: "mypkg.states:ProcessingState"
  Complete: "mypkg.states:CompleteState"
initial_state: InitialState
rules: []
```

The mapping:
- Keys are the registry names (used for lookups)
- Values are dotted paths (`module:ClassName`)
- All states are registered before `initial_state` is resolved
- `initial_state` can reference a key from the mapping or be a dotted path itself

## Persistence

Save and restore component state with the JSON persistence adapter:

```python
from flexiflow.extras import save_component, load_snapshot, restore_component

# Save current state
save_component(component, "state.json", metadata={"version": "1.0"})

# Later: restore from file
snapshot = load_snapshot("state.json")
restored = restore_component(snapshot, engine)
```

### What's persisted

- Component name
- Current state class name
- Rules list
- Optional user metadata

### What's NOT persisted

- Event subscriptions
- Handler functions
- Logger/event bus references (re-injected on restore)

### SQLite Persistence

For production use cases needing history and durability, use the SQLite adapter:

```python
import sqlite3
from flexiflow.extras import (
    save_snapshot_sqlite,
    load_latest_snapshot_sqlite,
    list_snapshots_sqlite,
)
from flexiflow.extras import ComponentSnapshot

conn = sqlite3.connect("state.db")

# Save a snapshot
snapshot = ComponentSnapshot(
    name="my_component",
    current_state="AwaitingConfirmation",
    rules=[{"key": "value"}],
    metadata={"version": "1.0"},
)
row_id = save_snapshot_sqlite(conn, snapshot)

# Load the latest snapshot for a component
latest = load_latest_snapshot_sqlite(conn, "my_component")

# List snapshot history
history = list_snapshots_sqlite(conn, "my_component", limit=10)
```

The SQLite adapter:
- Uses the same `ComponentSnapshot` model as JSON persistence
- Stores full history (not just latest state)
- Returns `None` for missing components (not an exception)
- Raises `ValueError` for corrupt JSON in stored rows

**Retention**: Snapshots accumulate indefinitely. Use `prune_snapshots_sqlite()` to clean up:

```python
from flexiflow.extras import prune_snapshots_sqlite

# Keep only the 10 most recent snapshots
deleted = prune_snapshots_sqlite(conn, "my_component", keep_last=10)
```

## Examples

See [`examples/embedded_app/`](examples/embedded_app/) for a complete working example showing:

- Custom states with state packs
- SQLite persistence with automatic snapshots on state change
- Observability event subscriptions
- Retention management with pruning

## Cookbook

### Embedded Usage Pattern

```python
import sqlite3
from flexiflow.component import AsyncComponent
from flexiflow.config_loader import ConfigLoader
from flexiflow.engine import FlexiFlowEngine
from flexiflow.state_machine import StateMachine
from flexiflow.extras import (
    ComponentSnapshot,
    load_latest_snapshot_sqlite,
    save_snapshot_sqlite,
    prune_snapshots_sqlite,
)

# Load config (registers custom states)
config = ConfigLoader.load_component_config("config.yaml")
conn = sqlite3.connect("state.db")
engine = FlexiFlowEngine()

# Restore or create component
snapshot = load_latest_snapshot_sqlite(conn, config.name)
if snapshot:
    component = AsyncComponent(
        name=snapshot.name,
        rules=list(snapshot.rules),
        state_machine=StateMachine.from_name(snapshot.current_state),
    )
else:
    component = AsyncComponent(
        name=config.name,
        rules=list(config.rules),
        state_machine=StateMachine.from_name(config.initial_state),
    )

engine.register(component)

# Save on every state change
async def on_state_changed(data):
    snapshot = ComponentSnapshot(
        name=data["component"],
        current_state=data["to_state"],
        rules=component.rules,
        metadata={},
    )
    save_snapshot_sqlite(conn, snapshot)
    prune_snapshots_sqlite(conn, data["component"], keep_last=50)

await engine.event_bus.subscribe("state.changed", "persister", on_state_changed)
```

### JSON vs SQLite Persistence

| Feature | JSON | SQLite |
|---------|------|--------|
| Single file | ✅ | ✅ |
| History | ❌ (overwrites) | ✅ (appends) |
| Retention | N/A | `prune_snapshots_sqlite()` |
| Restore | `load_snapshot()` | `load_latest_snapshot_sqlite()` |
| Best for | Dev/debugging | Production |

## Errors & Troubleshooting

FlexiFlow errors follow a structured format: **What / Why / Fix / Context**.

### Error Format

Every FlexiFlow error includes:

| Field | Purpose |
|-------|---------|
| **What** | What went wrong (first line) |
| **Why** | Explanation of the cause |
| **Fix** | Actionable guidance to resolve |
| **Context** | Debugging metadata (paths, types, values) |

### Example Errors

**State not found:**

```
Unknown state 'BadState' not found in registry.
Why: The state name was not registered. Available: InitialState, ProcessingRequest, AwaitingConfirmation (+2 more)
Fix: Check spelling or register the state with DEFAULT_REGISTRY.register() before use.
Context: state_name='BadState'
```

**Config error:**

```
Missing required field 'name' in config.
Why: The configuration file is missing a required field.
Fix: Add 'name: your_component_name' to the config file.
Context: path='config.yaml'
```

**Import error:**

```
Invalid dotted path 'mypkg.states.MyState'.
Why: Dotted paths must use ':' to separate module from symbol.
Fix: Use format 'module.path:ClassName' (e.g., 'mypkg.states:MyState').
Context: dotted_path='mypkg.states.MyState'
```

### Exception Hierarchy

```
FlexiFlowError (base)
├── ConfigError      # Configuration validation failures
├── StateError       # State registry/machine errors
├── PersistenceError # JSON/SQLite persistence errors
└── ImportError_     # Dotted path import failures
```

All exceptions inherit from `FlexiFlowError`, so you can catch broadly or specifically:

```python
from flexiflow import FlexiFlowError, StateError

try:
    sm = StateMachine.from_name("BadState")
except StateError as e:
    print(f"State issue: {e}")
except FlexiFlowError as e:
    print(f"FlexiFlow error: {e}")
```

### Reporting Issues

When filing a GitHub issue, **paste the full error message** including the Context line. This helps us reproduce and fix the problem faster.

## Config Introspection

Use `explain()` to validate a config file before loading it. This helps catch errors early and understand what FlexiFlow will do with your config.

```python
from flexiflow import explain

result = explain("config.yaml")

if result.is_valid:
    print("Config is valid!")
    print(f"Component: {result.name}")
    print(f"Initial state: {result.initial_state}")
    print(f"Rules: {result.rules_count}")
else:
    print("Config has errors:")
    for error in result.errors:
        print(f"  - {error.what}")
```

### What explain() Does

- Parses the YAML and validates structure
- Resolves all dotted paths (without registering states)
- Checks that initial_state exists
- Lists built-in and custom states
- Collects warnings and errors

### What explain() Does NOT Do

- Register states in the global registry
- Create components or state machines
- Raise exceptions (errors are collected, not thrown)

### Human-Readable Output

Use `result.format()` for a formatted explanation:

```python
result = explain("config.yaml")
print(result.format())
```

Output:
```
FlexiFlow Config Explanation
========================================
Source: config.yaml

Component:
  name: my_component
  initial_state: InitialState
  rules: 3 rule(s)

States:
  ✓ CustomState: mypkg.states:CustomState
  Built-in: AwaitingConfirmation, ErrorHandling, InitialState, ProcessingRequest

Warnings:
  ⚠ No rules defined
    Fix: Add rules if your component needs them.

Status: ✓ Valid - config will load successfully
```

This is especially useful for debugging CI failures or validating configs before deployment.
