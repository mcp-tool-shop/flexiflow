from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .event_manager import AsyncEventManager
from .logger import get_logger


@dataclass
class FlexiFlowEngine:
    logger: Any = field(default_factory=lambda: get_logger("flexiflow"))
    event_bus: AsyncEventManager = field(init=False)
    components: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.event_bus = AsyncEventManager(logger=self.logger)

    def register(self, component: Any) -> None:
        if getattr(component, "logger", None) is None:
            component.logger = self.logger
        if getattr(component, "event_bus", None) is None:
            component.event_bus = self.event_bus

        self.components[component.name] = component
        self.logger.info("Registered component: %s", component.name)

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None:
            loop.create_task(
                self.event_bus.publish(
                    "engine.component.registered",
                    {"component": component.name},
                )
            )

    async def register_async(self, component: Any) -> None:
        self.register(component)
        await self.event_bus.publish(
            "engine.component.registered",
            {"component": component.name},
        )

    def get(self, name: str) -> Optional[Any]:
        return self.components.get(name)
