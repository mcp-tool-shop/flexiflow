"""Tests for dotted path imports and custom state loading."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from flexiflow import ConfigError, ImportError_, StateError
from flexiflow.config_loader import ConfigLoader
from flexiflow.imports import load_symbol
from flexiflow.state_machine import DEFAULT_REGISTRY, StateMachine


# --- load_symbol tests ---


def test_load_symbol_valid():
    """load_symbol loads a class from a dotted path."""
    cls = load_symbol("fixture_states:FixtureInitial")
    assert cls.__name__ == "FixtureInitial"


def test_load_symbol_missing_colon():
    """load_symbol raises ImportError_ if ':' is missing."""
    with pytest.raises(ImportError_, match="Invalid dotted path"):
        load_symbol("fixture_states.FixtureInitial")


def test_load_symbol_empty_parts():
    """load_symbol raises ImportError_ if module or symbol is empty."""
    with pytest.raises(ImportError_, match="Invalid dotted path"):
        load_symbol(":FixtureInitial")

    with pytest.raises(ImportError_, match="Invalid dotted path"):
        load_symbol("fixture_states:")


def test_load_symbol_module_not_found():
    """load_symbol raises ImportError_ if module doesn't exist."""
    with pytest.raises(ImportError_, match="Module not found"):
        load_symbol("nonexistent.module:SomeClass")


def test_load_symbol_symbol_not_found():
    """load_symbol raises ImportError_ if symbol doesn't exist in module."""
    with pytest.raises(ImportError_, match="not found"):
        load_symbol("fixture_states:DoesNotExist")


# --- ConfigLoader dotted path tests ---


def test_dotted_initial_state_registers_and_normalizes(tmp_path: Path):
    """ConfigLoader with dotted initial_state registers and normalizes to class name."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        textwrap.dedent(
            """\
            name: test_component
            rules: []
            initial_state: "fixture_states:FixtureInitial"
            """
        ),
        encoding="utf-8",
    )

    cfg = ConfigLoader.load_component_config(config_file)

    # Normalized to class name
    assert cfg.initial_state == "FixtureInitial"

    # Registered in default registry
    assert "FixtureInitial" in DEFAULT_REGISTRY.names()

    # Can create state machine from it
    sm = StateMachine.from_name(cfg.initial_state)
    assert sm.current_state.__class__.__name__ == "FixtureInitial"


def test_dotted_initial_state_invalid_symbol_errors(tmp_path: Path):
    """ConfigLoader raises ValueError for non-existent symbol."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        textwrap.dedent(
            """\
            name: test_component
            rules: []
            initial_state: "fixture_states:DoesNotExist"
            """
        ),
        encoding="utf-8",
    )

    with pytest.raises(ImportError_, match="not found"):
        ConfigLoader.load_component_config(config_file)


def test_dotted_initial_state_not_a_state_errors(tmp_path: Path):
    """ConfigLoader raises ImportError_ if symbol is not a State subclass."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        textwrap.dedent(
            """\
            name: test_component
            rules: []
            initial_state: "fixture_states:NotAState"
            """
        ),
        encoding="utf-8",
    )

    with pytest.raises(ImportError_, match="Not a State subclass"):
        ConfigLoader.load_component_config(config_file)


def test_plain_initial_state_still_works(tmp_path: Path):
    """ConfigLoader still works with plain state names (no dotted path)."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        textwrap.dedent(
            """\
            name: test_component
            rules: []
            initial_state: "InitialState"
            """
        ),
        encoding="utf-8",
    )

    cfg = ConfigLoader.load_component_config(config_file)
    assert cfg.initial_state == "InitialState"

    # Can still create from default registry
    sm = StateMachine.from_name(cfg.initial_state)
    assert sm.current_state.__class__.__name__ == "InitialState"


# --- states: mapping tests (state packs) ---


def test_states_mapping_registers_all_states(tmp_path: Path):
    """states: mapping registers all dotted states up-front."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        textwrap.dedent(
            """\
            name: test_component
            rules: []
            states:
              FixtureInitial: "fixture_states:FixtureInitial"
              AnotherFixtureState: "fixture_states:AnotherFixtureState"
            initial_state: FixtureInitial
            """
        ),
        encoding="utf-8",
    )

    cfg = ConfigLoader.load_component_config(config_file)

    # Both states registered
    assert "FixtureInitial" in DEFAULT_REGISTRY.names()
    assert "AnotherFixtureState" in DEFAULT_REGISTRY.names()

    # initial_state normalized (not a dotted path, just the class name)
    assert cfg.initial_state == "FixtureInitial"

    # Can create state machines from both
    sm1 = StateMachine.from_name("FixtureInitial")
    assert sm1.current_state.__class__.__name__ == "FixtureInitial"

    sm2 = StateMachine.from_name("AnotherFixtureState")
    assert sm2.current_state.__class__.__name__ == "AnotherFixtureState"


def test_states_mapping_with_dotted_initial_state(tmp_path: Path):
    """states: mapping works with dotted initial_state."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        textwrap.dedent(
            """\
            name: test_component
            rules: []
            states:
              FixtureInitial: "fixture_states:FixtureInitial"
            initial_state: "fixture_states:AnotherFixtureState"
            """
        ),
        encoding="utf-8",
    )

    cfg = ConfigLoader.load_component_config(config_file)

    # Both registered (one from mapping, one from initial_state)
    assert "FixtureInitial" in DEFAULT_REGISTRY.names()
    assert "AnotherFixtureState" in DEFAULT_REGISTRY.names()

    # initial_state normalized to class name
    assert cfg.initial_state == "AnotherFixtureState"


def test_states_mapping_empty_allowed(tmp_path: Path):
    """Empty states: mapping is allowed (no-op)."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        textwrap.dedent(
            """\
            name: test_component
            rules: []
            states: {}
            initial_state: InitialState
            """
        ),
        encoding="utf-8",
    )

    cfg = ConfigLoader.load_component_config(config_file)
    assert cfg.initial_state == "InitialState"


def test_states_mapping_missing_colon_errors(tmp_path: Path):
    """states: mapping values must contain ':' (dotted path format)."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        textwrap.dedent(
            """\
            name: test_component
            rules: []
            states:
              BadState: "fixture_states.FixtureInitial"
            initial_state: InitialState
            """
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="Invalid dotted path"):
        ConfigLoader.load_component_config(config_file)


def test_states_mapping_not_a_state_errors(tmp_path: Path):
    """states: mapping rejects non-State subclasses."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        textwrap.dedent(
            """\
            name: test_component
            rules: []
            states:
              NotAState: "fixture_states:NotAState"
            initial_state: InitialState
            """
        ),
        encoding="utf-8",
    )

    with pytest.raises(ImportError_, match="Not a State subclass"):
        ConfigLoader.load_component_config(config_file)


def test_states_mapping_invalid_type_errors(tmp_path: Path):
    """states: must be a mapping, not a list or scalar."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        textwrap.dedent(
            """\
            name: test_component
            rules: []
            states:
              - "fixture_states:FixtureInitial"
            initial_state: InitialState
            """
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="wrong type"):
        ConfigLoader.load_component_config(config_file)


def test_states_mapping_non_string_key_errors(tmp_path: Path):
    """states: mapping keys must be strings."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        textwrap.dedent(
            """\
            name: test_component
            rules: []
            states:
              123: "fixture_states:FixtureInitial"
            initial_state: InitialState
            """
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="Invalid states entry"):
        ConfigLoader.load_component_config(config_file)
