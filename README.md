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
