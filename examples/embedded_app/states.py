"""Custom states for the embedded app example."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Tuple

from flexiflow.state_machine import State

if TYPE_CHECKING:
    from flexiflow.component import AsyncComponent


class Idle(State):
    """Initial state - waiting for work."""

    async def handle_message(
        self, message: Dict[str, Any], component: "AsyncComponent"
    ) -> Tuple[bool, State]:
        if message.get("type") == "start_job":
            return True, Processing()
        return False, self


class Processing(State):
    """Actively processing a job."""

    async def handle_message(
        self, message: Dict[str, Any], component: "AsyncComponent"
    ) -> Tuple[bool, State]:
        msg_type = message.get("type")

        if msg_type == "complete":
            return True, Complete()
        if msg_type == "fail":
            return True, Failed()
        if msg_type == "cancel":
            return True, Idle()

        return False, self


class Complete(State):
    """Job completed successfully."""

    async def handle_message(
        self, message: Dict[str, Any], component: "AsyncComponent"
    ) -> Tuple[bool, State]:
        if message.get("type") == "reset":
            return True, Idle()
        return False, self


class Failed(State):
    """Job failed."""

    async def handle_message(
        self, message: Dict[str, Any], component: "AsyncComponent"
    ) -> Tuple[bool, State]:
        if message.get("type") == "retry":
            return True, Processing()
        if message.get("type") == "reset":
            return True, Idle()
        return False, self
