from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def run_cli(*args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    """Run CLI as module to work in editable installs and CI."""
    cmd = [sys.executable, "-m", "flexiflow.cli", *args]
    return subprocess.run(cmd, capture_output=True, text=True, env=env)


def test_cli_register(example_config_yaml: Path):
    """Basic register command exits 0."""
    r = run_cli("register", "--config", str(example_config_yaml))
    assert r.returncode == 0, f"stdout: {r.stdout}\nstderr: {r.stderr}"


def test_cli_register_with_start(example_config_yaml: Path):
    """Register with --start flag exits 0."""
    r = run_cli("register", "--config", str(example_config_yaml), "--start")
    assert r.returncode == 0, f"stdout: {r.stdout}\nstderr: {r.stderr}"


def test_cli_handle_confirm(example_config_yaml: Path):
    """Handle command with confirm message exits 0."""
    r = run_cli(
        "handle", "--config", str(example_config_yaml),
        "confirm", "--content", "confirmed"
    )
    assert r.returncode == 0, f"stdout: {r.stdout}\nstderr: {r.stderr}"


def test_cli_update_rules(example_config_yaml: Path, example_rules_yaml: Path):
    """Update rules command exits 0."""
    r = run_cli(
        "update_rules", "--config", str(example_config_yaml),
        str(example_rules_yaml)
    )
    assert r.returncode == 0, f"stdout: {r.stdout}\nstderr: {r.stderr}"


def test_cli_env_fallback(example_config_yaml: Path):
    """CLI respects FLEXIFLOW_CONFIG env var when --config not provided."""
    env = dict(os.environ)
    env["FLEXIFLOW_CONFIG"] = str(example_config_yaml)
    r = run_cli("register", "--start", env=env)
    assert r.returncode == 0, f"stdout: {r.stdout}\nstderr: {r.stderr}"


def test_cli_missing_config_fails():
    """CLI fails gracefully when no config is provided."""
    # Clear FLEXIFLOW_CONFIG if set
    env = dict(os.environ)
    env.pop("FLEXIFLOW_CONFIG", None)
    r = run_cli("register", env=env)
    assert r.returncode != 0
    assert "No config provided" in r.stderr or "No config provided" in r.stdout
