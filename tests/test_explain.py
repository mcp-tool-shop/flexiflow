"""Tests for explain() config introspection."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from flexiflow import ConfigExplanation, Diagnostic, explain


class TestDiagnostic:
    """Tests for Diagnostic formatting."""

    def test_format_minimal(self):
        """Diagnostic with only what field formats correctly."""
        d = Diagnostic(level="warning", what="Something happened")
        formatted = d.format()
        assert "[WARNING] Something happened" in formatted

    def test_format_full(self):
        """Diagnostic with all fields formats correctly."""
        d = Diagnostic(
            level="error",
            what="Bad thing happened",
            why="Because reasons",
            fix="Do the fix",
            context={"key": "value"},
        )
        formatted = d.format()
        assert "[ERROR] Bad thing happened" in formatted
        assert "Why: Because reasons" in formatted
        assert "Fix: Do the fix" in formatted
        assert "key='value'" in formatted


class TestConfigExplanation:
    """Tests for ConfigExplanation structure."""

    def test_is_valid_no_errors(self):
        """is_valid returns True when no errors."""
        exp = ConfigExplanation(config_path="test.yaml")
        assert exp.is_valid is True

    def test_is_valid_with_errors(self):
        """is_valid returns False when errors present."""
        exp = ConfigExplanation(config_path="test.yaml")
        exp.errors.append(Diagnostic(level="error", what="Oops"))
        assert exp.is_valid is False

    def test_format_includes_status(self):
        """format() includes validity status."""
        exp = ConfigExplanation(
            config_path="test.yaml",
            name="test_component",
            initial_state="InitialState",
        )
        formatted = exp.format()
        assert "Valid" in formatted

    def test_format_shows_errors(self):
        """format() shows errors when present."""
        exp = ConfigExplanation(config_path="test.yaml")
        exp.errors.append(Diagnostic(level="error", what="Missing name"))
        formatted = exp.format()
        assert "Missing name" in formatted
        assert "Invalid" in formatted


class TestExplainValidConfigs:
    """Tests for explain() with valid configs."""

    def test_minimal_valid_config(self, tmp_path: Path):
        """Minimal valid config passes validation."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            textwrap.dedent(
                """\
                name: test_component
                rules: []
                initial_state: InitialState
                """
            ),
            encoding="utf-8",
        )

        result = explain(config_file)

        assert result.is_valid
        assert result.name == "test_component"
        assert result.initial_state == "InitialState"
        assert result.rules_count == 0
        assert len(result.errors) == 0

    def test_config_with_rules(self, tmp_path: Path):
        """Config with rules shows correct count."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            textwrap.dedent(
                """\
                name: test_component
                rules:
                  - key: value
                  - another: rule
                initial_state: InitialState
                """
            ),
            encoding="utf-8",
        )

        result = explain(config_file)

        assert result.is_valid
        assert result.rules_count == 2

    def test_config_with_state_pack(self, tmp_path: Path):
        """Config with states mapping resolves custom states."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            textwrap.dedent(
                """\
                name: test_component
                states:
                  FixtureInitial: "fixture_states:FixtureInitial"
                initial_state: FixtureInitial
                rules: []
                """
            ),
            encoding="utf-8",
        )

        result = explain(config_file)

        assert result.is_valid
        assert len(result.states) == 1
        assert result.states[0].key == "FixtureInitial"
        assert result.states[0].resolved is True
        assert result.states[0].is_state_subclass is True
        assert result.initial_state == "FixtureInitial"

    def test_builtin_states_listed(self, tmp_path: Path):
        """Builtin states are included in explanation."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            textwrap.dedent(
                """\
                name: test_component
                rules: []
                """
            ),
            encoding="utf-8",
        )

        result = explain(config_file)

        assert "InitialState" in result.builtin_states
        assert "ProcessingRequest" in result.builtin_states


class TestExplainInvalidConfigs:
    """Tests for explain() catching config errors."""

    def test_missing_file(self, tmp_path: Path):
        """Missing file is caught as error."""
        result = explain(tmp_path / "nonexistent.yaml")

        assert not result.is_valid
        assert len(result.errors) == 1
        assert "not found" in result.errors[0].what

    def test_invalid_yaml(self, tmp_path: Path):
        """Invalid YAML syntax is caught."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("name: [unclosed", encoding="utf-8")

        result = explain(config_file)

        assert not result.is_valid
        assert any("YAML" in e.what for e in result.errors)

    def test_missing_name(self, tmp_path: Path):
        """Missing name field is caught."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            textwrap.dedent(
                """\
                rules: []
                initial_state: InitialState
                """
            ),
            encoding="utf-8",
        )

        result = explain(config_file)

        assert not result.is_valid
        assert any("name" in e.what for e in result.errors)

    def test_wrong_type_name(self, tmp_path: Path):
        """Wrong type for name is caught."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            textwrap.dedent(
                """\
                name: 123
                rules: []
                """
            ),
            encoding="utf-8",
        )

        result = explain(config_file)

        assert not result.is_valid
        assert any("string" in e.what.lower() or "string" in (e.why or "").lower() for e in result.errors)

    def test_wrong_type_rules(self, tmp_path: Path):
        """Wrong type for rules is caught."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            textwrap.dedent(
                """\
                name: test
                rules: "not a list"
                """
            ),
            encoding="utf-8",
        )

        result = explain(config_file)

        assert not result.is_valid
        assert any("rules" in e.what.lower() for e in result.errors)

    def test_unknown_initial_state(self, tmp_path: Path):
        """Unknown initial_state is caught."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            textwrap.dedent(
                """\
                name: test
                rules: []
                initial_state: NonExistentState
                """
            ),
            encoding="utf-8",
        )

        result = explain(config_file)

        assert not result.is_valid
        assert any("NonExistentState" in e.what for e in result.errors)

    def test_invalid_dotted_path_format(self, tmp_path: Path):
        """Invalid dotted path format in states is caught."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            textwrap.dedent(
                """\
                name: test
                rules: []
                states:
                  BadState: "no_colon_here"
                initial_state: InitialState
                """
            ),
            encoding="utf-8",
        )

        result = explain(config_file)

        assert len(result.states) == 1
        assert result.states[0].resolved is False
        assert ":" in (result.states[0].error or "")

    def test_module_not_found(self, tmp_path: Path):
        """Non-existent module in dotted path is caught."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            textwrap.dedent(
                """\
                name: test
                rules: []
                states:
                  BadState: "nonexistent.module:SomeClass"
                initial_state: InitialState
                """
            ),
            encoding="utf-8",
        )

        result = explain(config_file)

        assert len(result.states) == 1
        assert result.states[0].resolved is False
        assert "not found" in (result.states[0].error or "").lower()

    def test_not_state_subclass(self, tmp_path: Path):
        """Symbol that isn't a State subclass is caught."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            textwrap.dedent(
                """\
                name: test
                rules: []
                states:
                  NotAState: "fixture_states:NotAState"
                initial_state: InitialState
                """
            ),
            encoding="utf-8",
        )

        result = explain(config_file)

        assert len(result.states) == 1
        assert result.states[0].resolved is True
        assert result.states[0].is_state_subclass is False


class TestExplainWarnings:
    """Tests for explain() warnings."""

    def test_empty_rules_warning(self, tmp_path: Path):
        """Empty rules list generates warning."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            textwrap.dedent(
                """\
                name: test_component
                rules: []
                initial_state: InitialState
                """
            ),
            encoding="utf-8",
        )

        result = explain(config_file)

        assert result.is_valid  # Warnings don't make it invalid
        assert any("rules" in w.what.lower() for w in result.warnings)


class TestExplainDictInput:
    """Tests for explain() with dict input."""

    def test_dict_input_valid(self):
        """explain() accepts dict input directly."""
        config = {
            "name": "test_component",
            "rules": [{"key": "value"}],
            "initial_state": "InitialState",
        }

        result = explain(config)

        assert result.is_valid
        assert result.name == "test_component"
        assert result.initial_state == "InitialState"
        assert result.rules_count == 1
        assert result.config_path == "(dict)"

    def test_dict_input_invalid(self):
        """explain() catches errors in dict input."""
        config = {
            "rules": [],  # missing name
            "initial_state": "NonExistentState",
        }

        result = explain(config)

        assert not result.is_valid
        assert any("name" in e.what.lower() for e in result.errors)


class TestExplainNoSideEffects:
    """Tests to verify explain() has no side effects."""

    def test_does_not_register_states(self, tmp_path: Path):
        """explain() does not register states in DEFAULT_REGISTRY."""
        from flexiflow import DEFAULT_REGISTRY

        # Get initial state count
        initial_states = set(DEFAULT_REGISTRY.names())

        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            textwrap.dedent(
                """\
                name: test_component
                states:
                  FixtureInitial: "fixture_states:FixtureInitial"
                initial_state: FixtureInitial
                rules: []
                """
            ),
            encoding="utf-8",
        )

        result = explain(config_file)
        assert result.is_valid

        # Check registry wasn't modified
        final_states = set(DEFAULT_REGISTRY.names())
        new_states = final_states - initial_states

        # FixtureInitial should NOT have been added
        assert "FixtureInitial" not in new_states or "FixtureInitial" in initial_states
