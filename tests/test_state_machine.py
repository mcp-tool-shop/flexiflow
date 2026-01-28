from __future__ import annotations

import pytest

from flexiflow import StateError
from flexiflow.state_machine import StateMachine, StateRegistry, State


class DummyComponent:
    """Minimal component stand-in for state machine tests."""
    pass


async def test_happy_path_transitions():
    """Full workflow: start → confirm → complete returns to InitialState."""
    sm = StateMachine.from_name("InitialState")
    c = DummyComponent()

    ok = await sm.handle_message({"type": "start"}, c)
    assert ok is True
    assert sm.current_state.__class__.__name__ == "AwaitingConfirmation"

    ok = await sm.handle_message({"type": "confirm", "content": "confirmed"}, c)
    assert ok is True
    assert sm.current_state.__class__.__name__ == "ProcessingRequest"

    ok = await sm.handle_message({"type": "complete"}, c)
    assert ok is True
    assert sm.current_state.__class__.__name__ == "InitialState"


async def test_error_path_transitions():
    """Error workflow: start → error → acknowledge returns to InitialState."""
    sm = StateMachine.from_name("InitialState")
    c = DummyComponent()

    await sm.handle_message({"type": "start"}, c)
    assert sm.current_state.__class__.__name__ == "AwaitingConfirmation"

    # From AwaitingConfirmation, need to get to ProcessingRequest first
    await sm.handle_message({"type": "confirm", "content": "confirmed"}, c)
    assert sm.current_state.__class__.__name__ == "ProcessingRequest"

    ok = await sm.handle_message({"type": "error"}, c)
    assert ok is True
    assert sm.current_state.__class__.__name__ == "ErrorHandling"

    ok = await sm.handle_message({"type": "acknowledge"}, c)
    assert ok is True
    assert sm.current_state.__class__.__name__ == "InitialState"


async def test_cancel_path_from_awaiting_confirmation():
    """Cancel from AwaitingConfirmation returns to InitialState."""
    sm = StateMachine.from_name("InitialState")
    c = DummyComponent()

    await sm.handle_message({"type": "start"}, c)
    assert sm.current_state.__class__.__name__ == "AwaitingConfirmation"

    ok = await sm.handle_message({"type": "cancel"}, c)
    assert ok is True
    assert sm.current_state.__class__.__name__ == "InitialState"


async def test_unknown_message_does_not_transition():
    """Unrecognized message type leaves state unchanged."""
    sm = StateMachine.from_name("InitialState")
    c = DummyComponent()

    ok = await sm.handle_message({"type": "nonsense"}, c)
    assert ok is False
    assert sm.current_state.__class__.__name__ == "InitialState"


async def test_confirm_without_correct_content_fails():
    """Confirm message requires content='confirmed' to proceed."""
    sm = StateMachine.from_name("InitialState")
    c = DummyComponent()

    await sm.handle_message({"type": "start"}, c)
    assert sm.current_state.__class__.__name__ == "AwaitingConfirmation"

    # Wrong content
    ok = await sm.handle_message({"type": "confirm", "content": "wrong"}, c)
    assert ok is False
    assert sm.current_state.__class__.__name__ == "AwaitingConfirmation"

    # Missing content
    ok = await sm.handle_message({"type": "confirm"}, c)
    assert ok is False
    assert sm.current_state.__class__.__name__ == "AwaitingConfirmation"


def test_registry_unknown_state_raises():
    """Requesting unknown state from registry raises StateError."""
    with pytest.raises(StateError, match="Unknown state"):
        StateMachine.from_name("NonExistentState")


def test_custom_registry_isolation():
    """Custom registry doesn't affect default registry."""
    custom = StateRegistry()

    class CustomState(State):
        async def handle_message(self, message, component):
            return True, self

    custom.register("CustomState", CustomState)

    sm = StateMachine.from_name("CustomState", registry=custom)
    assert sm.current_state.__class__.__name__ == "CustomState"

    # Default registry shouldn't have it
    with pytest.raises(StateError, match="Unknown state"):
        StateMachine.from_name("CustomState")
