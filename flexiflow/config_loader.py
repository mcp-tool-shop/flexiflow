from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from .errors import (
    ConfigError,
    ErrorContext,
    config_missing_field,
    config_wrong_type,
    import_not_state_subclass,
)
from .imports import load_symbol
from .state_machine import DEFAULT_REGISTRY, State


@dataclass(frozen=True)
class ComponentConfig:
    name: str
    rules: List[dict]
    initial_state: str = "InitialState"


class ConfigLoader:
    @staticmethod
    def load_yaml(path: str | Path) -> Dict[str, Any]:
        p = Path(path)
        with p.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if not isinstance(data, dict):
            raise config_wrong_type(
                field="(root)",
                expected="mapping/object",
                got=type(data).__name__,
                path=str(p),
            )
        return data

    @staticmethod
    def _register_dotted_state(
        dotted_path: str, config_path: Optional[str] = None
    ) -> str:
        """
        Load a state class from a dotted path and register it.

        Returns the normalized class name (registry key).
        """
        state_cls = load_symbol(dotted_path)

        if not isinstance(state_cls, type) or not issubclass(state_cls, State):
            raise import_not_state_subclass(dotted_path, type(state_cls).__name__)

        # Register under class name and return normalized name
        DEFAULT_REGISTRY.register(state_cls.__name__, state_cls)
        return state_cls.__name__

    @staticmethod
    def load_component_config(path: str | Path) -> ComponentConfig:
        path_str = str(path)
        data = ConfigLoader.load_yaml(path)

        name = data.get("name")
        if not name or not isinstance(name, str):
            raise config_missing_field("name", path_str)

        rules = data.get("rules", [])
        if rules is None:
            rules = []
        if not isinstance(rules, list):
            raise config_wrong_type("rules", "list", type(rules).__name__, path_str)

        # Process states: mapping first (register all dotted states up-front)
        states_mapping = data.get("states", {})
        if states_mapping is not None and not isinstance(states_mapping, dict):
            raise config_wrong_type(
                "states", "mapping", type(states_mapping).__name__, path_str
            )

        if states_mapping:
            for key, dotted_path in states_mapping.items():
                if not isinstance(key, str) or not isinstance(dotted_path, str):
                    ctx = ErrorContext()
                    ctx.add("config_path", path_str)
                    ctx.add("key", key)
                    ctx.add("value", dotted_path)
                    raise ConfigError(
                        f"Invalid states entry: {key!r}: {dotted_path!r}",
                        why="Both key and value in 'states' must be strings.",
                        fix="Use format: StateName: 'module:ClassName'",
                        context=ctx,
                    )
                if ":" not in dotted_path:
                    ctx = ErrorContext()
                    ctx.add("config_path", path_str)
                    ctx.add("key", key)
                    ctx.add("value", dotted_path)
                    raise ConfigError(
                        f"Invalid dotted path in states['{key}']: {dotted_path!r}",
                        why="State paths must be in 'module:ClassName' format.",
                        fix="Use format: StateName: 'mypackage.states:MyStateClass'",
                        context=ctx,
                    )
                ConfigLoader._register_dotted_state(dotted_path, path_str)

        # Process initial_state (may reference a state from the mapping or be a dotted path itself)
        initial_state = data.get("initial_state", "InitialState")
        if not isinstance(initial_state, str):
            raise config_wrong_type(
                "initial_state", "string", type(initial_state).__name__, path_str
            )

        # Handle dotted path imports (e.g., "mypkg.states:MyState")
        if ":" in initial_state:
            initial_state = ConfigLoader._register_dotted_state(initial_state, path_str)

        return ComponentConfig(name=name, rules=rules, initial_state=initial_state)

    @staticmethod
    def load_rules(path: str | Path) -> List[dict]:
        path_str = str(path)
        data = ConfigLoader.load_yaml(path)
        rules = data.get("rules", [])
        if rules is None:
            return []
        if not isinstance(rules, list):
            raise config_wrong_type("rules", "list", type(rules).__name__, path_str)
        return rules
