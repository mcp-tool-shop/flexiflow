from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .event_manager import AsyncEventManager
from .state_machine import StateMachine


@dataclass
class AsyncComponent:
    name: str
    rules: List[dict] = field(default_factory=list)
    state_machine: StateMachine = field(default_factory=lambda: StateMachine.from_name("InitialState"))
    logger: Any = None  # logging.Logger-like
    event_bus: Optional[AsyncEventManager] = None

    async def add_rule(self, rule: dict) -> None:
        self.rules.append(rule)

    async def update_rules(self, new_rules: List[dict]) -> None:
        self.rules.extend(new_rules)

    async def handle_message(self, message: Dict[str, Any]) -> None:
        proceeded = await self.state_machine.handle_message(message, self)
        if proceeded and self.logger:
            self.logger.info(
                "%s transitioned to %s",
                self.name,
                self.state_machine.current_state.__class__.__name__,
            )

        if proceeded and self.event_bus:
            await self.event_bus.publish(
                "state.changed",
                {"component": self.name, "state": self.state_machine.current_state.__class__.__name__},
            )
