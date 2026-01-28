"""Tests for pack_loader module."""

from __future__ import annotations

import pytest

from flexiflow import ConfigError, ImportError_
from flexiflow.pack_loader import collect_provided_keys, load_packs
from flexiflow.statepack import MappingPack, StateSpec, TransitionSpec


# --- Test fixtures ---


class DummyState:
    """Fake state class for testing."""

    pass


class AnotherState:
    """Another fake state class for testing."""

    pass


class SimplePack:
    """Simple StatePack implementation for testing."""

    @property
    def name(self) -> str:
        return "simple"

    def provides(self) -> dict[str, StateSpec]:
        return {"SimpleState": StateSpec(DummyState)}

    def transitions(self) -> list[TransitionSpec]:
        return []

    def depends_on(self) -> set[str]:
        return set()


class SessionPack:
    """Session StatePack for testing."""

    @property
    def name(self) -> str:
        return "session"

    def provides(self) -> dict[str, StateSpec]:
        return {
            "Idle": StateSpec(DummyState, "Waiting state"),
            "Active": StateSpec(AnotherState, "Working state"),
        }

    def transitions(self) -> list[TransitionSpec]:
        return [TransitionSpec("Idle", "start", "Active")]

    def depends_on(self) -> set[str]:
        return set()


class ConflictingPack:
    """Pack that provides 'Idle' for collision testing."""

    @property
    def name(self) -> str:
        return "conflicting"

    def provides(self) -> dict[str, StateSpec]:
        return {"Idle": StateSpec(DummyState)}

    def transitions(self) -> list[TransitionSpec]:
        return []

    def depends_on(self) -> set[str]:
        return set()


# --- Tests for legacy states: mapping ---


class TestLoadPacksLegacyStates:
    """Tests for load_packs with legacy states: mapping."""

    def test_empty_states_mapping(self):
        """Empty states mapping returns single MappingPack."""
        packs = load_packs(states={})
        assert len(packs) == 1
        assert isinstance(packs[0], MappingPack)
        assert packs[0].provides() == {}

    def test_states_mapping_wrapped_in_mappingpack(self):
        """States mapping is wrapped in MappingPack."""
        packs = load_packs(states={"Idle": DummyState, "Active": AnotherState})
        assert len(packs) == 1
        assert isinstance(packs[0], MappingPack)
        assert packs[0].name == "mapping"

        provides = packs[0].provides()
        assert "Idle" in provides
        assert "Active" in provides

    def test_states_mapping_preserves_classes(self):
        """States mapping preserves exact class references."""
        packs = load_packs(states={"Test": DummyState})
        spec = packs[0].provides()["Test"]
        assert spec.state_class is DummyState


# --- Tests for new packs: list ---


class TestLoadPacksInstances:
    """Tests for load_packs with StatePack instances."""

    def test_empty_packs_list(self):
        """Empty packs list returns empty result."""
        packs = load_packs(packs=[])
        assert packs == []

    def test_single_pack_instance(self):
        """Single pack instance passes through."""
        pack = SimplePack()
        result = load_packs(packs=[pack])
        assert len(result) == 1
        assert result[0] is pack

    def test_multiple_pack_instances(self):
        """Multiple pack instances pass through in order."""
        pack1 = SimplePack()
        pack2 = SessionPack()
        result = load_packs(packs=[pack1, pack2])
        assert len(result) == 2
        assert result[0] is pack1
        assert result[1] is pack2


class TestLoadPacksDottedPaths:
    """Tests for load_packs with dotted path strings."""

    def test_dotted_path_loads_pack(self):
        """Dotted path loads and instantiates pack class."""
        packs = load_packs(packs=["fixture_states:FixturePack"])
        assert len(packs) == 1
        assert packs[0].name == "fixture"
        assert "FixtureState" in packs[0].provides()

    def test_dotted_path_loads_instance(self):
        """Dotted path can load a pre-instantiated pack."""
        packs = load_packs(packs=["fixture_states:fixture_pack_instance"])
        assert len(packs) == 1
        assert packs[0].name == "fixture"

    def test_invalid_dotted_path_format_no_colon(self):
        """Dotted path without colon raises ImportError_."""
        with pytest.raises(ImportError_, match="Invalid pack path format"):
            load_packs(packs=["mypackage.packs.MyPack"])

    def test_invalid_dotted_path_empty_parts(self):
        """Dotted path with empty parts raises ImportError_."""
        with pytest.raises(ImportError_, match="Invalid pack path format"):
            load_packs(packs=[":MyPack"])

        with pytest.raises(ImportError_, match="Invalid pack path format"):
            load_packs(packs=["mypackage:"])

    def test_module_not_found(self):
        """Non-existent module raises ImportError_."""
        with pytest.raises(ImportError_, match="Module not found"):
            load_packs(packs=["nonexistent.module:SomePack"])

    def test_symbol_not_found(self):
        """Non-existent symbol raises ImportError_."""
        with pytest.raises(ImportError_, match="not found"):
            load_packs(packs=["fixture_states:NonExistentPack"])

    def test_not_a_statepack(self):
        """Symbol that isn't a StatePack raises ConfigError."""
        # fixture_states:NotAState is a plain class, not a StatePack
        with pytest.raises(ConfigError, match="Not a StatePack"):
            load_packs(packs=["fixture_states:NotAState"])


class TestLoadPacksInvalidInput:
    """Tests for load_packs with invalid input."""

    def test_cannot_have_both_states_and_packs(self):
        """Cannot specify both states and packs."""
        with pytest.raises(ConfigError, match="Cannot specify both"):
            load_packs(states={"Test": DummyState}, packs=[SimplePack()])

    def test_invalid_pack_entry_type(self):
        """Invalid pack entry type raises ConfigError."""
        with pytest.raises(ConfigError, match="Invalid pack entry"):
            load_packs(packs=[123])  # type: ignore

        with pytest.raises(ConfigError, match="Invalid pack entry"):
            load_packs(packs=[["nested", "list"]])  # type: ignore


# --- Tests for collision detection ---


class TestCollisionDetection:
    """Tests for collision detection in load_packs."""

    def test_duplicate_keys_across_packs(self):
        """Duplicate keys across packs raises ConfigError."""
        pack1 = SessionPack()  # provides Idle, Active
        pack2 = ConflictingPack()  # provides Idle

        with pytest.raises(ConfigError, match="Duplicate state key.*Idle"):
            load_packs(packs=[pack1, pack2])

    def test_shadowing_builtin(self):
        """Pack shadowing builtin key raises ConfigError."""
        pack = SessionPack()  # provides Idle, Active

        with pytest.raises(ConfigError, match="shadows builtin"):
            load_packs(packs=[pack], builtin_keys={"Idle"})

    def test_no_collision_with_different_keys(self):
        """Packs with different keys don't collide."""
        pack1 = SimplePack()  # provides SimpleState
        pack2 = SessionPack()  # provides Idle, Active

        # Should not raise
        result = load_packs(packs=[pack1, pack2])
        assert len(result) == 2

    def test_no_collision_with_non_overlapping_builtins(self):
        """Packs don't collide with non-overlapping builtins."""
        pack = SimplePack()  # provides SimpleState

        # Should not raise - SimpleState doesn't overlap with these builtins
        result = load_packs(packs=[pack], builtin_keys={"InitialState", "ErrorState"})
        assert len(result) == 1


# --- Tests for collect_provided_keys ---


class TestCollectProvidedKeys:
    """Tests for collect_provided_keys helper."""

    def test_empty_packs(self):
        """Empty packs list returns empty dict."""
        result = collect_provided_keys([])
        assert result == {}

    def test_single_pack(self):
        """Single pack's keys are collected with attribution."""
        pack = SessionPack()
        result = collect_provided_keys([pack])

        assert result == {"Idle": "session", "Active": "session"}

    def test_multiple_packs(self):
        """Multiple packs' keys are collected with correct attribution."""
        pack1 = SimplePack()
        pack2 = SessionPack()
        result = collect_provided_keys([pack1, pack2])

        assert result["SimpleState"] == "simple"
        assert result["Idle"] == "session"
        assert result["Active"] == "session"


# --- Tests for determinism ---


class TestDeterminism:
    """Tests for deterministic behavior."""

    def test_packs_order_preserved(self):
        """Packs are returned in input order."""
        pack1 = SimplePack()
        pack2 = SessionPack()

        result = load_packs(packs=[pack1, pack2])
        assert result[0] is pack1
        assert result[1] is pack2

        # Reverse order
        result2 = load_packs(packs=[pack2, pack1])
        assert result2[0] is pack2
        assert result2[1] is pack1

    def test_provided_keys_deterministic(self):
        """collect_provided_keys returns deterministic results."""
        pack = SessionPack()
        result1 = collect_provided_keys([pack])
        result2 = collect_provided_keys([pack])

        assert result1 == result2
