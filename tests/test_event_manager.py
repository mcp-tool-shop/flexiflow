from __future__ import annotations

import pytest

from flexiflow.event_manager import AsyncEventManager, SubscriptionHandle


async def test_priority_order_sequential():
    """Handlers execute in ascending priority order (1 before 3)."""
    bus = AsyncEventManager()
    seen = []

    async def h1(_):
        seen.append("p1")

    async def h3(_):
        seen.append("p3")

    await bus.subscribe("x", "c1", h3, priority=3)
    await bus.subscribe("x", "c2", h1, priority=1)

    await bus.publish("x")
    assert seen == ["p1", "p3"]


async def test_filter_blocks_and_allows():
    """Filter predicate gates which events reach the handler."""
    bus = AsyncEventManager()
    seen = []

    async def h(_):
        seen.append("hit")

    await bus.subscribe("x", "c", h, filter_fn=lambda name, data: data == 42)

    await bus.publish("x", 0)
    await bus.publish("x", 42)

    assert seen == ["hit"]


async def test_no_subscribers_is_noop():
    """Publishing to an event with no subscribers doesn't raise."""
    bus = AsyncEventManager()
    # Should not raise
    await bus.publish("missing", {"a": 1})


async def test_on_error_continue_sequential_runs_all():
    """With on_error='continue', subsequent handlers still run after an error."""
    bus = AsyncEventManager()
    seen = []

    async def bad(_):
        seen.append("bad")
        raise RuntimeError("boom")

    async def good(_):
        seen.append("good")

    await bus.subscribe("x", "c1", bad, priority=1)
    await bus.subscribe("x", "c2", good, priority=2)

    await bus.publish("x", on_error="continue")
    assert seen == ["bad", "good"]


async def test_on_error_raise_sequential_stops():
    """With on_error='raise', first exception propagates and stops execution."""
    bus = AsyncEventManager()
    seen = []

    async def bad(_):
        seen.append("bad")
        raise RuntimeError("boom")

    async def good(_):
        seen.append("good")

    await bus.subscribe("x", "c1", bad, priority=1)
    await bus.subscribe("x", "c2", good, priority=2)

    with pytest.raises(RuntimeError):
        await bus.publish("x", on_error="raise")

    assert seen == ["bad"]


async def test_concurrent_delivery_runs_all_handlers():
    """Concurrent mode runs all handlers (order not guaranteed for completion)."""
    bus = AsyncEventManager()
    seen = []

    async def h1(_):
        seen.append("h1")

    async def h2(_):
        seen.append("h2")

    async def h3(_):
        seen.append("h3")

    await bus.subscribe("x", "c1", h1, priority=1)
    await bus.subscribe("x", "c2", h2, priority=2)
    await bus.subscribe("x", "c3", h3, priority=3)

    await bus.publish("x", delivery="concurrent")

    # All three should have run (order may vary in concurrent mode)
    assert sorted(seen) == ["h1", "h2", "h3"]


async def test_priority_validation():
    """Priority must be between 1 and 5."""
    bus = AsyncEventManager()

    async def h(_):
        pass

    with pytest.raises(ValueError, match="priority must be"):
        await bus.subscribe("x", "c", h, priority=0)

    with pytest.raises(ValueError, match="priority must be"):
        await bus.subscribe("x", "c", h, priority=6)


# --- Unsubscribe tests ---


async def test_subscribe_returns_handle():
    """subscribe() returns a SubscriptionHandle."""
    bus = AsyncEventManager()

    async def h(_):
        pass

    handle = await bus.subscribe("x", "c", h)
    assert isinstance(handle, SubscriptionHandle)
    assert handle.event_name == "x"
    assert handle.subscription_id  # non-empty uuid string


async def test_unsubscribe_removes_handler():
    """unsubscribe(handle) prevents handler from being called."""
    bus = AsyncEventManager()
    seen = []

    async def h(_):
        seen.append("hit")

    handle = await bus.subscribe("x", "c", h)
    removed = bus.unsubscribe(handle)

    assert removed is True
    await bus.publish("x")
    assert seen == []


async def test_unsubscribe_idempotent():
    """unsubscribe() is safe to call multiple times."""
    bus = AsyncEventManager()

    async def h(_):
        pass

    handle = await bus.subscribe("x", "c", h)

    assert bus.unsubscribe(handle) is True
    assert bus.unsubscribe(handle) is False  # already removed
    assert bus.unsubscribe(handle) is False  # still idempotent


def test_unsubscribe_unknown_handle():
    """unsubscribe() with unknown handle returns False."""
    bus = AsyncEventManager()
    fake_handle = SubscriptionHandle(event_name="x", subscription_id="nonexistent")
    assert bus.unsubscribe(fake_handle) is False


async def test_unsubscribe_all_component():
    """unsubscribe_all(component_name) removes all handlers for that component."""
    bus = AsyncEventManager()
    seen = []

    async def h1(_):
        seen.append("h1")

    async def h2(_):
        seen.append("h2")

    async def other(_):
        seen.append("other")

    await bus.subscribe("event1", "comp_a", h1)
    await bus.subscribe("event2", "comp_a", h2)
    await bus.subscribe("event1", "comp_b", other)

    removed_count = bus.unsubscribe_all("comp_a")
    assert removed_count == 2

    await bus.publish("event1")
    await bus.publish("event2")

    # Only comp_b's handler should have fired
    assert seen == ["other"]


async def test_unsubscribe_all_unknown_component():
    """unsubscribe_all() with unknown component returns 0."""
    bus = AsyncEventManager()
    assert bus.unsubscribe_all("nonexistent") == 0
