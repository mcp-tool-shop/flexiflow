from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import yaml


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

        initial_state = data.get("initial_state", "InitialState")
        if not isinstance(initial_state, str):
            raise ValueError("'initial_state' must be a string")

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
