"""Tests for flow visualization."""

import pytest

from flexiflow import visualize
from flexiflow.explain import ConfigExplanation, PackInfo, explain
from flexiflow.statepack import TransitionSpec
from flexiflow.visualize import _generate_mermaid, _sanitize_id


class TestVisualize:
    """Tests for the main visualize() function."""

    def test_visualize_returns_string(self):
        """visualize() returns a string."""
        config = {"name": "test", "initial_state": "InitialState"}
        result = visualize(config)
        assert isinstance(result, str)

    def test_visualize_starts_with_flowchart(self):
        """Output starts with 'flowchart LR'."""
        config = {"name": "test", "initial_state": "InitialState"}
        result = visualize(config)
        assert result.startswith("flowchart LR")

    def test_visualize_unsupported_format_raises(self):
        """Unsupported format raises ValueError."""
        config = {"name": "test", "initial_state": "InitialState"}
        with pytest.raises(ValueError, match="Unsupported format"):
            visualize(config, format="graphviz")

    def test_visualize_accepts_config_explanation(self):
        """visualize() accepts a pre-built ConfigExplanation."""
        exp = ConfigExplanation(config_path="(test)")
        result = visualize(exp)
        assert result.startswith("flowchart LR")

    def test_visualize_accepts_dict(self):
        """visualize() accepts a config dict."""
        config = {"name": "test", "initial_state": "InitialState"}
        result = visualize(config)
        assert "flowchart LR" in result


class TestMermaidGeneration:
    """Tests for Mermaid flowchart generation."""

    def test_empty_packs_produces_minimal_output(self):
        """Empty packs produce minimal flowchart."""
        exp = ConfigExplanation(config_path="(test)")
        result = _generate_mermaid(exp)
        assert result.startswith("flowchart LR")
        # Should have legend and resolution policy in meta
        assert "%% Edge labels: on_message [guard]" in result
        assert "initial_state_resolution" in result

    def test_pack_order_in_meta_comments(self):
        """Pack order appears in meta comments."""
        exp = ConfigExplanation(
            config_path="(test)",
            pack_order=["auth", "session"],
        )
        result = _generate_mermaid(exp)
        assert "%% pack_order: auth, session" in result

    def test_resolution_policy_in_meta_comments(self):
        """Resolution policy appears in meta comments."""
        exp = ConfigExplanation(
            config_path="(test)",
            initial_state_resolution=["builtin", "packs"],
        )
        result = _generate_mermaid(exp)
        assert "%% initial_state_resolution: [builtin, packs]" in result

    def test_single_pack_creates_subgraph(self):
        """Single pack creates a subgraph."""
        exp = ConfigExplanation(
            config_path="(test)",
            packs=[
                PackInfo(
                    name="session",
                    provided_keys=["SessionIdle", "SessionActive"],
                    transitions=[],
                    depends_on=[],
                ),
            ],
        )
        result = _generate_mermaid(exp)
        assert 'subgraph session["pack: session"]' in result
        assert 'SessionIdle["SessionIdle"]' in result
        assert 'SessionActive["SessionActive"]' in result
        assert "end" in result

    def test_multiple_packs_create_multiple_subgraphs(self):
        """Multiple packs create multiple subgraphs."""
        exp = ConfigExplanation(
            config_path="(test)",
            packs=[
                PackInfo(
                    name="auth",
                    provided_keys=["AuthIdle"],
                    transitions=[],
                    depends_on=[],
                ),
                PackInfo(
                    name="session",
                    provided_keys=["SessionActive"],
                    transitions=[],
                    depends_on=[],
                ),
            ],
        )
        result = _generate_mermaid(exp)
        assert 'subgraph auth["pack: auth"]' in result
        assert 'subgraph session["pack: session"]' in result

    def test_transitions_create_edges(self):
        """Transitions create edge arrows."""
        exp = ConfigExplanation(
            config_path="(test)",
            packs=[
                PackInfo(
                    name="session",
                    provided_keys=["SessionIdle", "SessionActive"],
                    transitions=[
                        TransitionSpec("SessionIdle", "start", "SessionActive"),
                    ],
                    depends_on=[],
                ),
            ],
        )
        result = _generate_mermaid(exp)
        assert 'SessionIdle -->|"start"| SessionActive' in result

    def test_multiple_transitions(self):
        """Multiple transitions create multiple edges."""
        exp = ConfigExplanation(
            config_path="(test)",
            packs=[
                PackInfo(
                    name="session",
                    provided_keys=["SessionIdle", "SessionActive"],
                    transitions=[
                        TransitionSpec("SessionIdle", "start", "SessionActive"),
                        TransitionSpec("SessionActive", "complete", "SessionIdle"),
                    ],
                    depends_on=[],
                ),
            ],
        )
        result = _generate_mermaid(exp)
        assert 'SessionIdle -->|"start"| SessionActive' in result
        assert 'SessionActive -->|"complete"| SessionIdle' in result

    def test_transition_with_guard(self):
        """Transitions with guards include guard in label."""
        exp = ConfigExplanation(
            config_path="(test)",
            packs=[
                PackInfo(
                    name="session",
                    provided_keys=["SessionIdle", "SessionActive"],
                    transitions=[
                        TransitionSpec(
                            "SessionActive", "timeout", "SessionIdle", guard="is_expired"
                        ),
                    ],
                    depends_on=[],
                ),
            ],
        )
        result = _generate_mermaid(exp)
        assert '-->|"timeout [is_expired]"|' in result


class TestUnknownStates:
    """Tests for handling unknown/missing state references."""

    def test_unknown_to_state_creates_unknown_subgraph(self):
        """Transition to unknown state creates unknown subgraph."""
        exp = ConfigExplanation(
            config_path="(test)",
            packs=[
                PackInfo(
                    name="broken",
                    provided_keys=["StartState"],
                    transitions=[
                        TransitionSpec("StartState", "go", "NonExistentState"),
                    ],
                    depends_on=[],
                ),
            ],
        )
        result = _generate_mermaid(exp)
        assert 'subgraph unknown["unknown states"]' in result
        assert 'NonExistentState' in result
        assert ":::unknown" in result

    def test_unknown_from_state_creates_unknown_subgraph(self):
        """Transition from unknown state creates unknown subgraph."""
        exp = ConfigExplanation(
            config_path="(test)",
            packs=[
                PackInfo(
                    name="broken",
                    provided_keys=["EndState"],
                    transitions=[
                        TransitionSpec("UnknownSource", "arrive", "EndState"),
                    ],
                    depends_on=[],
                ),
            ],
        )
        result = _generate_mermaid(exp)
        assert 'subgraph unknown["unknown states"]' in result
        assert "UnknownSource" in result

    def test_unknown_style_class_defined(self):
        """Unknown states get the 'unknown' style class."""
        exp = ConfigExplanation(
            config_path="(test)",
            packs=[
                PackInfo(
                    name="broken",
                    provided_keys=["StartState"],
                    transitions=[
                        TransitionSpec("StartState", "go", "MissingState"),
                    ],
                    depends_on=[],
                ),
            ],
        )
        result = _generate_mermaid(exp)
        assert "classDef unknown stroke-dasharray: 5 5" in result

    def test_no_unknown_subgraph_when_all_states_known(self):
        """No unknown subgraph when all transition states are known."""
        exp = ConfigExplanation(
            config_path="(test)",
            packs=[
                PackInfo(
                    name="session",
                    provided_keys=["StateA", "StateB"],
                    transitions=[
                        TransitionSpec("StateA", "go", "StateB"),
                    ],
                    depends_on=[],
                ),
            ],
        )
        result = _generate_mermaid(exp)
        assert "unknown" not in result.lower() or "unknown states" not in result

    def test_builtin_states_not_marked_unknown(self):
        """Transitions to builtin states are not marked as unknown."""
        exp = ConfigExplanation(
            config_path="(test)",
            builtin_states=["InitialState", "ErrorState"],
            packs=[
                PackInfo(
                    name="session",
                    provided_keys=["ActiveState"],
                    transitions=[
                        TransitionSpec("ActiveState", "fail", "ErrorState"),
                    ],
                    depends_on=[],
                ),
            ],
        )
        result = _generate_mermaid(exp)
        # ErrorState is builtin, so no unknown subgraph needed
        assert 'subgraph unknown["unknown states"]' not in result


class TestSanitizeId:
    """Tests for ID sanitization."""

    def test_alphanumeric_unchanged(self):
        """Alphanumeric names pass through unchanged."""
        assert _sanitize_id("SessionIdle") == "SessionIdle"

    def test_underscores_preserved(self):
        """Underscores are preserved."""
        assert _sanitize_id("session_idle") == "session_idle"

    def test_spaces_replaced(self):
        """Spaces are replaced with underscores."""
        assert _sanitize_id("session idle") == "session_idle"

    def test_special_chars_replaced(self):
        """Special characters are replaced with underscores."""
        assert _sanitize_id("state-name.v2") == "state_name_v2"

    def test_empty_returns_node(self):
        """Empty string returns 'node'."""
        assert _sanitize_id("") == "node"


class TestIntegration:
    """Integration tests using real pack fixtures."""

    def test_visualize_session_pack(self):
        """Visualize a real pack with transitions."""
        config = {
            "name": "test",
            "initial_state": "SessionIdle",
            "packs": ["fixture_states:session_pack_instance"],
        }
        result = visualize(config)

        # Check structure
        assert "flowchart LR" in result
        assert 'subgraph session["pack: session"]' in result
        assert "SessionIdle" in result
        assert "SessionActive" in result

        # Check transitions (quoted labels for Mermaid 11.x)
        assert '-->|"start"|' in result
        assert '-->|"complete"|' in result
        assert '-->|"timeout [is_expired]"|' in result

    def test_visualize_broken_pack_shows_unknown(self):
        """Visualize pack with unknown state references."""
        config = {
            "name": "test",
            "initial_state": "BrokenStart",
            "packs": ["fixture_states:broken_pack_instance"],
        }
        result = visualize(config)

        # Check structure
        assert "flowchart LR" in result
        assert 'subgraph broken["pack: broken"]' in result

        # Check unknown states appear
        assert 'subgraph unknown["unknown states"]' in result
        assert "NonExistentState" in result
        assert "UnknownSource" in result
        assert "classDef unknown" in result

    def test_visualize_empty_pack_no_subgraph(self):
        """Empty pack (no provided keys) doesn't create subgraph."""
        exp = ConfigExplanation(
            config_path="(test)",
            packs=[
                PackInfo(
                    name="empty",
                    provided_keys=[],
                    transitions=[],
                    depends_on=[],
                ),
            ],
        )
        result = _generate_mermaid(exp)
        # No subgraph for empty pack
        assert 'subgraph empty' not in result


class TestEdgeCases:
    """Edge case tests."""

    def test_quotes_in_message_escaped(self):
        """Quote characters in message labels are escaped."""
        exp = ConfigExplanation(
            config_path="(test)",
            packs=[
                PackInfo(
                    name="test",
                    provided_keys=["A", "B"],
                    transitions=[
                        TransitionSpec("A", 'say "hello"', "B"),
                    ],
                    depends_on=[],
                ),
            ],
        )
        result = _generate_mermaid(exp)
        # Quotes should be escaped, label should be quoted
        assert r'-->|"say \"hello\""|' in result

    def test_no_trailing_newline(self):
        """Output doesn't end with trailing newlines."""
        exp = ConfigExplanation(config_path="(test)")
        result = _generate_mermaid(exp)
        assert not result.endswith("\n")

    def test_pack_name_with_spaces_sanitized(self):
        """Pack names with spaces are sanitized for subgraph ID."""
        exp = ConfigExplanation(
            config_path="(test)",
            packs=[
                PackInfo(
                    name="my pack",
                    provided_keys=["State1"],
                    transitions=[],
                    depends_on=[],
                ),
            ],
        )
        result = _generate_mermaid(exp)
        # Subgraph ID should be sanitized, but label keeps original
        assert 'subgraph my_pack["pack: my pack"]' in result
