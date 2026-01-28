"""FlexiFlow - A lightweight async component engine with events and state machines.

Quick Start:
    from flexiflow import FlexiFlowEngine, AsyncComponent, StateMachine, State

    class MyState(State):
        async def handle_message(self, message, component):
            if message.get("type") == "done":
                return True, MyState()
            return False, self

    engine = FlexiFlowEngine()
    component = AsyncComponent(
        name="my_component",
        state_machine=StateMachine(current_state=MyState()),
    )
    engine.register(component)
    await component.handle_message({"type": "done"})

For config-driven usage:
    from flexiflow import ConfigLoader, AsyncComponent, StateMachine, FlexiFlowEngine

    config = ConfigLoader.load_component_config("config.yaml")
    component = AsyncComponent(
        name=config.name,
        rules=list(config.rules),
        state_machine=StateMachine.from_name(config.initial_state),
    )
"""

from .component import AsyncComponent
from .config_loader import ComponentConfig, ConfigLoader
from .engine import FlexiFlowEngine
from .errors import (
    ConfigError,
    FlexiFlowError,
    ImportError_,
    PersistenceError,
    StateError,
)
from .state_machine import DEFAULT_REGISTRY, State, StateRegistry, StateMachine

__all__ = [
    # Core
    "FlexiFlowEngine",
    "AsyncComponent",
    "StateMachine",
    "State",
    # Config
    "ConfigLoader",
    "ComponentConfig",
    # Registry (advanced)
    "StateRegistry",
    "DEFAULT_REGISTRY",
    # Errors
    "FlexiFlowError",
    "ConfigError",
    "StateError",
    "PersistenceError",
    "ImportError_",
]

__version__ = "0.3.1"
