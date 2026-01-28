"""Config explanation and validation without side effects.

explain(config_path) answers: "What does FlexiFlow think this config means,
and will it work?" — without executing or mutating anything.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml

from .errors import ErrorContext, FlexiFlowError
from .state_machine import DEFAULT_REGISTRY, State


@dataclass
class Diagnostic:
    """A single warning or error from config explanation."""

    level: str  # "warning" or "error"
    what: str
    why: Optional[str] = None
    fix: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)

    def format(self) -> str:
        """Format as structured message (matches FlexiFlowError format)."""
        lines = [f"[{self.level.upper()}] {self.what}"]
        if self.why:
            lines.append(f"Why: {self.why}")
        if self.fix:
            lines.append(f"Fix: {self.fix}")
        if self.context:
            ctx_lines = [f"  {k}={v!r}" for k, v in self.context.items()]
            lines.append("Context:\n" + "\n".join(ctx_lines))
        return "\n".join(lines)


@dataclass
class StateResolution:
    """Resolution details for a single state."""

    key: str  # Registry key name
    dotted_path: Optional[str]  # Original dotted path, if any
    resolved: bool  # Whether it resolved successfully
    is_state_subclass: bool  # Whether it's a valid State subclass
    error: Optional[str] = None  # Error message if failed


@dataclass
class ConfigExplanation:
    """Structured explanation of a FlexiFlow config."""

    # Source
    config_path: str

    # Normalized config values
    name: Optional[str] = None
    initial_state: Optional[str] = None
    rules_count: int = 0

    # State resolution
    states: List[StateResolution] = field(default_factory=list)
    builtin_states: List[str] = field(default_factory=list)

    # Diagnostics
    warnings: List[Diagnostic] = field(default_factory=list)
    errors: List[Diagnostic] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """True if config has no errors (warnings are ok)."""
        return len(self.errors) == 0

    def format(self) -> str:
        """Format as human-readable explanation."""
        lines = [
            "FlexiFlow Config Explanation",
            "=" * 40,
            f"Source: {self.config_path}",
            "",
        ]

        # Component info
        lines.append("Component:")
        lines.append(f"  name: {self.name or '(missing)'}")
        lines.append(f"  initial_state: {self.initial_state or '(missing)'}")
        lines.append(f"  rules: {self.rules_count} rule(s)")
        lines.append("")

        # States (sorted for deterministic output)
        lines.append("States:")
        if self.states:
            for s in sorted(self.states, key=lambda x: x.key):
                status = "✓" if s.resolved and s.is_state_subclass else "✗"
                if s.dotted_path:
                    lines.append(f"  {status} {s.key}: {s.dotted_path}")
                else:
                    lines.append(f"  {status} {s.key}")
                if s.error:
                    lines.append(f"      Error: {s.error}")
        else:
            lines.append("  (no custom states)")

        lines.append(f"  Built-in: {', '.join(sorted(self.builtin_states))}")
        lines.append("")

        # Diagnostics
        if self.warnings:
            lines.append("Warnings:")
            for w in self.warnings:
                lines.append(f"  ⚠ {w.what}")
                if w.fix:
                    lines.append(f"    Fix: {w.fix}")
            lines.append("")

        if self.errors:
            lines.append("Errors:")
            for e in self.errors:
                lines.append(f"  ✗ {e.what}")
                if e.why:
                    lines.append(f"    Why: {e.why}")
                if e.fix:
                    lines.append(f"    Fix: {e.fix}")
            lines.append("")

        # Summary
        if self.is_valid:
            lines.append("Status: ✓ Valid - config will load successfully")
        else:
            lines.append(f"Status: ✗ Invalid - {len(self.errors)} error(s) found")

        return "\n".join(lines)


def _try_import_symbol(dotted: str) -> tuple[Any, Optional[str]]:
    """Try to import a symbol, returning (symbol, error_msg)."""
    if ":" not in dotted:
        return None, f"Invalid format: missing ':' separator"

    module_path, symbol_name = dotted.split(":", 1)
    module_path = module_path.strip()
    symbol_name = symbol_name.strip()

    if not module_path or not symbol_name:
        return None, f"Invalid format: empty module or symbol"

    try:
        module = importlib.import_module(module_path)
    except Exception as e:
        return None, f"Module not found: {module_path}"

    try:
        return getattr(module, symbol_name), None
    except AttributeError:
        return None, f"Symbol '{symbol_name}' not found in '{module_path}'"


def explain(config: Union[str, Path, Dict[str, Any]]) -> ConfigExplanation:
    """
    Explain what a config means and validate it without side effects.

    This function:
    - Parses the YAML (if path) or uses dict directly
    - Resolves all dotted paths (without registering)
    - Validates all fields
    - Returns a structured report

    It does NOT:
    - Register states in DEFAULT_REGISTRY
    - Create components
    - Raise exceptions (errors are collected in the report)

    Args:
        config: Path to YAML config file, or a config dict directly

    Returns:
        ConfigExplanation with all diagnostics
    """
    # Handle dict input directly
    if isinstance(config, dict):
        result = ConfigExplanation(config_path="(dict)")
        result.builtin_states = DEFAULT_REGISTRY.names()
        data = config
        return _validate_config_data(result, data)

    # Handle path input
    path = Path(config)
    result = ConfigExplanation(config_path=str(path))

    # Collect built-in states
    result.builtin_states = DEFAULT_REGISTRY.names()

    # Try to load YAML
    if not path.exists():
        result.errors.append(
            Diagnostic(
                level="error",
                what=f"Config file not found: {path}",
                fix="Check the path and ensure the file exists.",
                context={"path": result.config_path},
            )
        )
        return result

    try:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        result.errors.append(
            Diagnostic(
                level="error",
                what="Invalid YAML syntax",
                why=str(e),
                fix="Check the file for YAML syntax errors.",
                context={"path": result.config_path},
            )
        )
        return result

    return _validate_config_data(result, data)


def _validate_config_data(
    result: ConfigExplanation, data: Any
) -> ConfigExplanation:
    """Validate config data and populate result with diagnostics."""
    if not isinstance(data, dict):
        result.errors.append(
            Diagnostic(
                level="error",
                what="Config must be a YAML mapping",
                why=f"Got {type(data).__name__} instead of mapping.",
                fix="Ensure your config file has key: value pairs at the top level.",
                context={"path": result.config_path, "got_type": type(data).__name__},
            )
        )
        return result

    # Validate name
    name = data.get("name")
    if not name:
        result.errors.append(
            Diagnostic(
                level="error",
                what="Missing required field: 'name'",
                why="Every component config must have a name.",
                fix="Add 'name: your_component_name' to your config.",
                context={"path": result.config_path},
            )
        )
    elif not isinstance(name, str):
        result.errors.append(
            Diagnostic(
                level="error",
                what="Field 'name' must be a string",
                why=f"Got {type(name).__name__}.",
                fix="Change 'name' to a string value.",
                context={"path": result.config_path, "got_type": type(name).__name__},
            )
        )
    else:
        result.name = name

    # Validate rules
    rules = data.get("rules", [])
    if rules is None:
        rules = []
    if not isinstance(rules, list):
        result.errors.append(
            Diagnostic(
                level="error",
                what="Field 'rules' must be a list",
                why=f"Got {type(rules).__name__}.",
                fix="Change 'rules' to a list (or remove it for empty rules).",
                context={"path": result.config_path, "got_type": type(rules).__name__},
            )
        )
    else:
        result.rules_count = len(rules)

    # Validate states mapping
    states_mapping = data.get("states", {})
    if states_mapping is not None and not isinstance(states_mapping, dict):
        result.errors.append(
            Diagnostic(
                level="error",
                what="Field 'states' must be a mapping",
                why=f"Got {type(states_mapping).__name__}.",
                fix="Use format: states:\n  StateName: 'module:ClassName'",
                context={"path": result.config_path, "got_type": type(states_mapping).__name__},
            )
        )
        states_mapping = {}

    # Resolve each state in the mapping
    if states_mapping:
        for key, dotted_path in states_mapping.items():
            if not isinstance(key, str) or not isinstance(dotted_path, str):
                result.states.append(
                    StateResolution(
                        key=str(key),
                        dotted_path=str(dotted_path) if dotted_path else None,
                        resolved=False,
                        is_state_subclass=False,
                        error="Both key and value must be strings",
                    )
                )
                continue

            if ":" not in dotted_path:
                result.states.append(
                    StateResolution(
                        key=key,
                        dotted_path=dotted_path,
                        resolved=False,
                        is_state_subclass=False,
                        error="Missing ':' separator (use 'module:ClassName' format)",
                    )
                )
                continue

            symbol, error = _try_import_symbol(dotted_path)
            if error:
                result.states.append(
                    StateResolution(
                        key=key,
                        dotted_path=dotted_path,
                        resolved=False,
                        is_state_subclass=False,
                        error=error,
                    )
                )
            elif not isinstance(symbol, type) or not issubclass(symbol, State):
                result.states.append(
                    StateResolution(
                        key=key,
                        dotted_path=dotted_path,
                        resolved=True,
                        is_state_subclass=False,
                        error=f"Not a State subclass (got {type(symbol).__name__})",
                    )
                )
            else:
                result.states.append(
                    StateResolution(
                        key=key,
                        dotted_path=dotted_path,
                        resolved=True,
                        is_state_subclass=True,
                    )
                )

    # Validate initial_state
    initial_state = data.get("initial_state", "InitialState")
    if not isinstance(initial_state, str):
        result.errors.append(
            Diagnostic(
                level="error",
                what="Field 'initial_state' must be a string",
                why=f"Got {type(initial_state).__name__}.",
                fix="Change 'initial_state' to a string value.",
                context={"path": result.config_path, "got_type": type(initial_state).__name__},
            )
        )
    else:
        # Resolve initial_state
        if ":" in initial_state:
            # Dotted path - try to import
            symbol, error = _try_import_symbol(initial_state)
            if error:
                result.errors.append(
                    Diagnostic(
                        level="error",
                        what=f"Cannot resolve initial_state: {initial_state}",
                        why=error,
                        fix="Check the module path and class name.",
                        context={"path": result.config_path, "initial_state": initial_state},
                    )
                )
            elif not isinstance(symbol, type) or not issubclass(symbol, State):
                result.errors.append(
                    Diagnostic(
                        level="error",
                        what=f"initial_state is not a State subclass",
                        why=f"'{initial_state}' resolved to {type(symbol).__name__}.",
                        fix="Ensure your class inherits from flexiflow.State.",
                        context={"path": result.config_path, "initial_state": initial_state},
                    )
                )
            else:
                result.initial_state = symbol.__name__
        else:
            # Plain state name - check if it exists
            state_keys = [s.key for s in result.states if s.resolved and s.is_state_subclass]
            all_valid = result.builtin_states + state_keys

            if initial_state in all_valid:
                result.initial_state = initial_state
            else:
                result.errors.append(
                    Diagnostic(
                        level="error",
                        what=f"Unknown initial_state: '{initial_state}'",
                        why="The state is not registered and not in the states mapping.",
                        fix=f"Use one of: {', '.join(all_valid[:5])}",
                        context={"path": result.config_path, "initial_state": initial_state},
                    )
                )

    # Add warnings for common issues
    if result.rules_count == 0 and result.is_valid:
        result.warnings.append(
            Diagnostic(
                level="warning",
                what="No rules defined",
                fix="Add rules if your component needs them.",
            )
        )

    # Check for failed state resolutions
    failed_states = [s for s in result.states if not s.resolved or not s.is_state_subclass]
    for s in failed_states:
        result.errors.append(
            Diagnostic(
                level="error",
                what=f"State '{s.key}' failed to resolve",
                why=s.error,
                fix="Check the dotted path and ensure the module is importable.",
                context={"key": s.key, "dotted_path": s.dotted_path},
            )
        )

    return result
