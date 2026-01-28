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
from .explain import ConfigExplanation, Diagnostic, explain
from .pack_loader import collect_provided_keys, load_packs
from .state_machine import DEFAULT_REGISTRY, State, StateRegistry, StateMachine
from .statepack import MappingPack, StateSpec, StatePack, TransitionSpec
from .visualize import visualize

__all__ = [
    # Core
    "FlexiFlowEngine",
    "AsyncComponent",
    "StateMachine",
    "State",
    # Config
    "ConfigLoader",
    "ComponentConfig",
    # StatePacks (public types for users defining packs)
    "StatePack",
    "StateSpec",
    "TransitionSpec",
    # Registry (advanced)
    "StateRegistry",
    "DEFAULT_REGISTRY",
    # Errors
    "FlexiFlowError",
    "ConfigError",
    "StateError",
    "PersistenceError",
    "ImportError_",
    # Introspection
    "explain",
    "ConfigExplanation",
    "Diagnostic",
    # Visualization
    "visualize",
]

# Internal imports available but not in __all__:
# - load_packs, collect_provided_keys: internal pack loading machinery
# - MappingPack: internal adapter for legacy states: dict format
# - PackInfo: internal dataclass for ConfigExplanation.packs

__version__ = "0.4.0"
