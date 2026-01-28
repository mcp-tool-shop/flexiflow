from __future__ import annotations

from flexiflow.engine import FlexiFlowEngine
from flexiflow.component import AsyncComponent
from flexiflow.state_machine import StateMachine


def test_register_attaches_logger_and_bus():
    """Engine injects logger and event_bus into registered components."""
    engine = FlexiFlowEngine()
    c = AsyncComponent(
        name="test_component",
        rules=[],
        state_machine=StateMachine.from_name("InitialState"),
    )

    # Before registration, component has no logger/event_bus
    assert c.logger is None
    assert c.event_bus is None

    engine.register(c)

    # After registration, engine's logger and event_bus are injected
    assert engine.get("test_component") is c
    assert c.logger is engine.logger
    assert c.event_bus is engine.event_bus


def test_get_returns_none_for_unknown():
    """get() returns None for unregistered component names."""
    engine = FlexiFlowEngine()
    assert engine.get("nonexistent") is None


def test_multiple_components():
    """Engine can register and retrieve multiple components."""
    engine = FlexiFlowEngine()

    c1 = AsyncComponent(name="comp1", state_machine=StateMachine.from_name("InitialState"))
    c2 = AsyncComponent(name="comp2", state_machine=StateMachine.from_name("InitialState"))

    engine.register(c1)
    engine.register(c2)

    assert engine.get("comp1") is c1
    assert engine.get("comp2") is c2
    assert len(engine.components) == 2
