"""Flow visualization from config introspection.

Generates diagrams from explain() data without side effects.
No runtime dependencies - purely manifest/introspection based.

Example:
    from flexiflow import visualize

    # Generate Mermaid diagram
    mermaid_source = visualize("config.yaml")
    print(mermaid_source)

    # Or from a dict
    mermaid_source = visualize({"name": "example", "packs": [...]})
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Set, Union

from .explain import ConfigExplanation, PackInfo, explain
from .statepack import TransitionSpec


def visualize(
    config: Union[str, Path, Dict[str, Any], ConfigExplanation],
    *,
    format: str = "mermaid",
) -> str:
    """Generate a diagram from config introspection.

    Uses explain() internally to extract pack info, states, and transitions.
    No side effects - purely reads config and generates diagram source.

    Args:
        config: Path to YAML config, config dict, or existing ConfigExplanation.
        format: Output format. Currently only "mermaid" is supported.

    Returns:
        Diagram source string (e.g., Mermaid flowchart).

    Raises:
        ValueError: If format is not supported.

    Example:
        >>> mermaid = visualize("config.yaml")
        >>> print(mermaid)
        flowchart LR
        subgraph session["pack: session"]
          SessionIdle["SessionIdle"]
          SessionActive["SessionActive"]
        end
        SessionIdle -->|start| SessionActive
    """
    if format != "mermaid":
        raise ValueError(f"Unsupported format: {format!r}. Use 'mermaid'.")

    # Get or create explanation
    if isinstance(config, ConfigExplanation):
        explanation = config
    else:
        explanation = explain(config)

    return _generate_mermaid(explanation)


def _generate_mermaid(exp: ConfigExplanation) -> str:
    """Generate Mermaid flowchart from ConfigExplanation.

    Uses flowchart LR with pack subgraphs for best readability.
    """
    lines: List[str] = []
    lines.append("flowchart LR")
    lines.append("")

    # Legend and meta comments
    lines.append("%% Edge labels: on_message [guard]")
    if exp.pack_order:
        lines.append(f"%% pack_order: {', '.join(exp.pack_order)}")
    if exp.initial_state_resolution:
        policy_str = ", ".join(exp.initial_state_resolution)
        lines.append(f"%% initial_state_resolution: [{policy_str}]")
    if exp.pack_order or exp.initial_state_resolution:
        lines.append("")

    # Collect all known states (from packs)
    known_states: Set[str] = set()
    for pack in exp.packs:
        known_states.update(pack.provided_keys)

    # Add builtin states as known
    known_states.update(exp.builtin_states)

    # Collect all transitions and find unknown states
    all_transitions: List[TransitionSpec] = []
    unknown_states: Set[str] = set()

    for pack in exp.packs:
        for trans in pack.transitions:
            all_transitions.append(trans)
            if trans.from_state not in known_states:
                unknown_states.add(trans.from_state)
            if trans.to_state not in known_states:
                unknown_states.add(trans.to_state)

    # Generate pack subgraphs
    for pack in exp.packs:
        if not pack.provided_keys:
            continue

        # Sanitize pack name for subgraph ID (no spaces, special chars)
        safe_id = _sanitize_id(pack.name)
        lines.append(f'subgraph {safe_id}["pack: {pack.name}"]')

        for key in sorted(pack.provided_keys):
            safe_key = _sanitize_id(key)
            lines.append(f'  {safe_key}["{key}"]')

        lines.append("end")
        lines.append("")

    # Generate unknown states subgraph (if any)
    if unknown_states:
        lines.append('subgraph unknown["unknown states"]')
        for key in sorted(unknown_states):
            safe_key = _sanitize_id(f"unknown_{key}")
            lines.append(f'  {safe_key}["{key}"]:::unknown')
        lines.append("end")
        lines.append("")

    # Generate transitions
    if all_transitions:
        for trans in all_transitions:
            from_id = _get_node_id(trans.from_state, known_states, unknown_states)
            to_id = _get_node_id(trans.to_state, known_states, unknown_states)

            # Build label - escape quotes and special chars for Mermaid
            label = trans.on_message.replace('"', '\\"')

            # Add guard if present
            if trans.guard:
                label = f"{label} [{trans.guard}]"

            # Always quote edge labels for Mermaid 11.x compatibility
            lines.append(f'{from_id} -->|"{label}"| {to_id}')

        lines.append("")

    # Add class definition for unknown states
    if unknown_states:
        lines.append("%% Styling for unknown states")
        lines.append("classDef unknown stroke-dasharray: 5 5, stroke: #999")
        lines.append("")

    # Remove trailing empty line
    while lines and lines[-1] == "":
        lines.pop()

    return "\n".join(lines)


def _sanitize_id(name: str) -> str:
    """Convert a name to a valid Mermaid node ID.

    Mermaid IDs should be alphanumeric with underscores.
    """
    # Replace non-alphanumeric chars with underscores
    result = []
    for char in name:
        if char.isalnum() or char == "_":
            result.append(char)
        else:
            result.append("_")
    return "".join(result) or "node"


def _get_node_id(state: str, known: Set[str], unknown: Set[str]) -> str:
    """Get the Mermaid node ID for a state.

    Known states use their sanitized name directly.
    Unknown states are prefixed with 'unknown_'.
    """
    if state in unknown:
        return _sanitize_id(f"unknown_{state}")
    return _sanitize_id(state)
