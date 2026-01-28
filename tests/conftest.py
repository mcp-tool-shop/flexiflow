from __future__ import annotations

import textwrap
from pathlib import Path

import pytest


@pytest.fixture
def example_config_yaml(tmp_path: Path) -> Path:
    p = tmp_path / "config.yaml"
    p.write_text(
        textwrap.dedent(
            """\
            name: example_component
            rules:
              - rule1: "..."
            initial_state: "InitialState"
            """
        ),
        encoding="utf-8",
    )
    return p


@pytest.fixture
def example_rules_yaml(tmp_path: Path) -> Path:
    p = tmp_path / "new_rules.yaml"
    p.write_text(
        textwrap.dedent(
            """\
            rules:
              - rule2: "..."
              - rule3: "..."
            """
        ),
        encoding="utf-8",
    )
    return p
