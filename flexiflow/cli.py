from __future__ import annotations

import argparse
import asyncio
import os

from .config_loader import ConfigLoader
from .component import AsyncComponent
from .engine import FlexiFlowEngine
from .logger import get_logger
from .state_machine import StateMachine


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="FlexiFlow CLI")
    sub = p.add_subparsers(dest="command", required=True)

    reg = sub.add_parser("register", help="Register a component from config.")
    reg.add_argument("--config", type=str, default=None, help="Path to config YAML (or use FLEXIFLOW_CONFIG).")
    reg.add_argument("--start", action="store_true", help="Send a 'start' message after registration.")

    handle = sub.add_parser("handle", help="Send a message to a component.")
    handle.add_argument("--config", type=str, default=None, help="Path to config YAML (or use FLEXIFLOW_CONFIG).")
    handle.add_argument("message_type", type=str, help="Message type")
    handle.add_argument("--content", type=str, default="", help="Optional message content")

    upd = sub.add_parser("update_rules", help="Update component rules from a rules YAML.")
    upd.add_argument("--config", type=str, default=None, help="Path to config YAML (or use FLEXIFLOW_CONFIG).")
    upd.add_argument("rule_file", type=str, help="Path to rules YAML containing 'rules:' list.")

    return p


def _resolve_config_path(cli_value: str | None) -> str:
    path = cli_value or os.getenv("FLEXIFLOW_CONFIG")
    if not path:
        raise SystemExit("No config provided. Use --config or set FLEXIFLOW_CONFIG.")
    return path


async def cmd_register(args) -> None:
    config_path = _resolve_config_path(args.config)
    cfg = ConfigLoader.load_component_config(config_path)

    logger = get_logger("flexiflow")
    engine = FlexiFlowEngine(logger=logger)

    component = AsyncComponent(
        name=cfg.name,
        rules=list(cfg.rules),
        state_machine=StateMachine.from_name(cfg.initial_state),
        logger=logger,
    )
    engine.register(component)

    if args.start:
        await component.handle_message({"type": "start"})


async def cmd_handle(args) -> None:
    config_path = _resolve_config_path(args.config)
    cfg = ConfigLoader.load_component_config(config_path)

    logger = get_logger("flexiflow")
    engine = FlexiFlowEngine(logger=logger)

    component = AsyncComponent(
        name=cfg.name,
        rules=list(cfg.rules),
        state_machine=StateMachine.from_name(cfg.initial_state),
        logger=logger,
    )
    engine.register(component)

    msg = {"type": args.message_type}
    if args.content:
        msg["content"] = args.content

    await component.handle_message(msg)


async def cmd_update_rules(args) -> None:
    config_path = _resolve_config_path(args.config)
    cfg = ConfigLoader.load_component_config(config_path)

    logger = get_logger("flexiflow")
    engine = FlexiFlowEngine(logger=logger)

    component = AsyncComponent(
        name=cfg.name,
        rules=list(cfg.rules),
        state_machine=StateMachine.from_name(cfg.initial_state),
        logger=logger,
    )
    engine.register(component)

    new_rules = ConfigLoader.load_rules(args.rule_file)
    await component.update_rules(new_rules)
    logger.info("%s rules updated. Total rules: %d", component.name, len(component.rules))


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "register":
        asyncio.run(cmd_register(args))
    elif args.command == "handle":
        asyncio.run(cmd_handle(args))
    elif args.command == "update_rules":
        asyncio.run(cmd_update_rules(args))
    else:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
