"""Tests for structured error messages.

These tests verify that errors follow the what/why/fix/context contract
and that the formatting doesn't regress.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from flexiflow import (
    ConfigError,
    FlexiFlowError,
    ImportError_,
    PersistenceError,
    StateError,
)
from flexiflow.errors import (
    ErrorContext,
    config_missing_field,
    config_wrong_type,
    import_invalid_format,
    import_module_not_found,
    import_not_state_subclass,
    import_symbol_not_found,
    persistence_invalid_json,
    persistence_missing_field,
    state_not_found,
)


# --- ErrorContext tests ---


def test_error_context_empty():
    """Empty context formats to empty string."""
    ctx = ErrorContext()
    assert ctx.format() == ""


def test_error_context_single_item():
    """Single item formats correctly."""
    ctx = ErrorContext()
    ctx.add("path", "/foo/bar")
    assert "path='/foo/bar'" in ctx.format()


def test_error_context_chaining():
    """add() returns self for chaining."""
    ctx = ErrorContext().add("a", 1).add("b", 2)
    formatted = ctx.format()
    assert "a=1" in formatted
    assert "b=2" in formatted


# --- FlexiFlowError base tests ---


def test_flexiflow_error_what_only():
    """Error with only 'what' formats correctly."""
    err = FlexiFlowError("Something went wrong")
    assert str(err) == "Something went wrong"


def test_flexiflow_error_full():
    """Error with all fields formats correctly."""
    ctx = ErrorContext().add("key", "value")
    err = FlexiFlowError(
        "Something went wrong",
        why="Because reasons",
        fix="Do this instead",
        context=ctx,
    )
    msg = str(err)
    assert "Something went wrong" in msg
    assert "Why: Because reasons" in msg
    assert "Fix: Do this instead" in msg
    assert "key='value'" in msg


def test_error_inheritance():
    """All error types inherit from FlexiFlowError."""
    assert issubclass(ConfigError, FlexiFlowError)
    assert issubclass(StateError, FlexiFlowError)
    assert issubclass(PersistenceError, FlexiFlowError)
    assert issubclass(ImportError_, FlexiFlowError)


# --- config_missing_field tests ---


def test_config_missing_field_message():
    """config_missing_field includes what/why/fix."""
    err = config_missing_field("name", "/path/to/config.yaml")
    msg = str(err)
    assert "missing required field" in msg.lower()
    assert "'name'" in msg
    assert "Why:" in msg
    assert "Fix:" in msg
    assert "config_path" in msg


def test_config_missing_field_is_config_error():
    """config_missing_field returns ConfigError."""
    err = config_missing_field("name")
    assert isinstance(err, ConfigError)


# --- config_wrong_type tests ---


def test_config_wrong_type_message():
    """config_wrong_type includes expected vs got."""
    err = config_wrong_type("rules", "list", "str", "/config.yaml")
    msg = str(err)
    assert "wrong type" in msg.lower()
    assert "list" in msg
    assert "str" in msg


# --- state_not_found tests ---


def test_state_not_found_message():
    """state_not_found includes valid states."""
    err = state_not_found("BadState", ["InitialState", "ProcessingRequest"])
    msg = str(err)
    assert "Unknown state" in msg
    assert "'BadState'" in msg
    assert "InitialState" in msg
    assert "ProcessingRequest" in msg


def test_state_not_found_truncates_long_list():
    """state_not_found truncates when many states."""
    states = [f"State{i}" for i in range(20)]
    err = state_not_found("BadState", states)
    msg = str(err)
    # Should show first 5 + "more" indicator
    assert "+15 more" in msg or "(+15 more)" in msg


def test_state_not_found_is_state_error():
    """state_not_found returns StateError."""
    err = state_not_found("BadState", ["Good"])
    assert isinstance(err, StateError)


# --- import error tests ---


def test_import_invalid_format_message():
    """import_invalid_format explains correct format."""
    err = import_invalid_format("mymodule.MyClass")
    msg = str(err)
    assert "Invalid dotted path" in msg
    assert "module:ClassName" in msg.lower() or "colon" in msg.lower()


def test_import_module_not_found_message():
    """import_module_not_found includes module name."""
    err = import_module_not_found("nonexistent.module", "nonexistent.module:Class")
    msg = str(err)
    assert "Module not found" in msg
    assert "nonexistent.module" in msg


def test_import_symbol_not_found_message():
    """import_symbol_not_found includes module and symbol."""
    err = import_symbol_not_found("mymodule", "BadClass", "mymodule:BadClass")
    msg = str(err)
    assert "not found" in msg.lower()
    assert "BadClass" in msg
    assert "mymodule" in msg


def test_import_not_state_subclass_message():
    """import_not_state_subclass explains the fix."""
    err = import_not_state_subclass("mymodule:NotAState", "function")
    msg = str(err)
    assert "Not a State subclass" in msg
    assert "flexiflow.State" in msg or "inherit" in msg.lower()


# --- persistence error tests ---


def test_persistence_invalid_json_message():
    """persistence_invalid_json includes path."""
    err = persistence_invalid_json("/path/to/state.json", "Expecting value")
    msg = str(err)
    assert "Invalid JSON" in msg
    assert "/path/to/state.json" in msg


def test_persistence_missing_field_message():
    """persistence_missing_field includes field name."""
    err = persistence_missing_field("/state.json", "current_state")
    msg = str(err)
    assert "missing" in msg.lower()
    assert "current_state" in msg


# --- Integration tests with actual code paths ---


def test_state_registry_raises_structured_error():
    """StateRegistry.create raises StateError with structured message."""
    from flexiflow.state_machine import StateRegistry

    registry = StateRegistry()
    registry.register("OnlyState", type("OnlyState", (), {}))

    with pytest.raises(StateError) as exc_info:
        registry.create("NonExistent")

    msg = str(exc_info.value)
    assert "Unknown state" in msg
    assert "NonExistent" in msg
    assert "Why:" in msg
    assert "Fix:" in msg


def test_config_loader_raises_structured_error(tmp_path: Path):
    """ConfigLoader raises ConfigError with structured message."""
    from flexiflow.config_loader import ConfigLoader

    # Create config without required 'name' field
    config_file = tmp_path / "bad.yaml"
    config_file.write_text("rules: []\n", encoding="utf-8")

    with pytest.raises(ConfigError) as exc_info:
        ConfigLoader.load_component_config(config_file)

    msg = str(exc_info.value)
    assert "missing" in msg.lower()
    assert "name" in msg


def test_import_raises_structured_error():
    """load_symbol raises ImportError_ with structured message."""
    from flexiflow.imports import load_symbol

    with pytest.raises(ImportError_) as exc_info:
        load_symbol("nonexistent.module:Thing")

    msg = str(exc_info.value)
    assert "Module not found" in msg
    assert "Why:" in msg
    assert "Fix:" in msg
