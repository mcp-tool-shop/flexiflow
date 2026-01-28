from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import yaml

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
            raise ValueError(f"Config must be a mapping/object. Got: {type(data).__name__}")
        return data

    @staticmethod
    def _register_dotted_state(dotted_path: str) -> str:
        """
        Load a state class from a dotted path and register it.

        Returns the normalized class name (registry key).
        """
        state_cls = load_symbol(dotted_path)

        if not isinstance(state_cls, type) or not issubclass(state_cls, State):
            raise ValueError(
                f"State path must point to a State subclass, got {state_cls!r}"
            )

        # Register under class name and return normalized name
        DEFAULT_REGISTRY.register(state_cls.__name__, state_cls)
        return state_cls.__name__

    @staticmethod
    def load_component_config(path: str | Path) -> ComponentConfig:
        data = ConfigLoader.load_yaml(path)

        name = data.get("name")
        if not name or not isinstance(name, str):
            raise ValueError("Config missing required string field: 'name'")

        rules = data.get("rules", [])
        if rules is None:
            rules = []
        if not isinstance(rules, list):
            raise ValueError("'rules' must be a list")

        # Process states: mapping first (register all dotted states up-front)
        states_mapping = data.get("states", {})
        if states_mapping is not None and not isinstance(states_mapping, dict):
            raise ValueError("'states' must be a mapping")

        if states_mapping:
            for key, dotted_path in states_mapping.items():
                if not isinstance(key, str) or not isinstance(dotted_path, str):
                    raise ValueError(
                        f"'states' entries must be string: string, got {key!r}: {dotted_path!r}"
                    )
                if ":" not in dotted_path:
                    raise ValueError(
                        f"'states' values must be dotted paths (module:Class), got {dotted_path!r}"
                    )
                ConfigLoader._register_dotted_state(dotted_path)

        # Process initial_state (may reference a state from the mapping or be a dotted path itself)
        initial_state = data.get("initial_state", "InitialState")
        if not isinstance(initial_state, str):
            raise ValueError("'initial_state' must be a string")

        # Handle dotted path imports (e.g., "mypkg.states:MyState")
        if ":" in initial_state:
            initial_state = ConfigLoader._register_dotted_state(initial_state)

        return ComponentConfig(name=name, rules=rules, initial_state=initial_state)

    @staticmethod
    def load_rules(path: str | Path) -> List[dict]:
        data = ConfigLoader.load_yaml(path)
        rules = data.get("rules", [])
        if rules is None:
            return []
        if not isinstance(rules, list):
            raise ValueError("'rules' must be a list")
        return rules
