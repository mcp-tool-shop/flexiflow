"""Tests for public API stability.

These tests ensure the top-level imports remain valid and don't regress.
"""

from __future__ import annotations


def test_core_imports_from_top_level():
    """Core symbols are importable from flexiflow directly."""
    from flexiflow import (
        AsyncComponent,
        FlexiFlowEngine,
        State,
        StateMachine,
    )

    # Verify they're the real classes
    assert FlexiFlowEngine.__name__ == "FlexiFlowEngine"
    assert AsyncComponent.__name__ == "AsyncComponent"
    assert StateMachine.__name__ == "StateMachine"
    assert State.__name__ == "State"


def test_config_imports_from_top_level():
    """Config symbols are importable from flexiflow directly."""
    from flexiflow import ComponentConfig, ConfigLoader

    assert ConfigLoader.__name__ == "ConfigLoader"
    assert ComponentConfig.__name__ == "ComponentConfig"


def test_registry_imports_from_top_level():
    """Registry symbols are importable from flexiflow directly."""
    from flexiflow import DEFAULT_REGISTRY, StateRegistry

    assert StateRegistry.__name__ == "StateRegistry"
    assert isinstance(DEFAULT_REGISTRY, StateRegistry)


def test_statepack_types_from_top_level():
    """StatePack types are importable from flexiflow directly."""
    from flexiflow import StatePack, StateSpec, TransitionSpec

    # StatePack is a Protocol
    assert StatePack.__name__ == "StatePack"

    # StateSpec and TransitionSpec are dataclasses
    assert StateSpec.__name__ == "StateSpec"
    assert TransitionSpec.__name__ == "TransitionSpec"

    # Can create instances
    class DummyState:
        pass

    spec = StateSpec(DummyState, "test description")
    assert spec.state_class is DummyState
    assert spec.description == "test description"

    trans = TransitionSpec("A", "msg", "B")
    assert trans.from_state == "A"
    assert trans.on_message == "msg"
    assert trans.to_state == "B"


def test_version_available():
    """Version string is accessible."""
    import flexiflow

    assert hasattr(flexiflow, "__version__")
    assert isinstance(flexiflow.__version__, str)
    assert flexiflow.__version__.count(".") >= 2  # semver-ish


def test_all_exports_are_importable():
    """All symbols in __all__ are actually importable."""
    import flexiflow

    for name in flexiflow.__all__:
        obj = getattr(flexiflow, name, None)
        assert obj is not None, f"'{name}' in __all__ but not importable"
