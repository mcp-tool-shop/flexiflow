from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Tuple, Type

from .errors import state_not_found

Message = Dict[str, Any]


class State:
    async def handle_message(self, message: Message, component: Any) -> Tuple[bool, "State"]:
        raise NotImplementedError


class StateRegistry:
    def __init__(self) -> None:
        self._states: Dict[str, Type[State]] = {}

    def register(self, name: str, state_cls: Type[State]) -> None:
        self._states[name] = state_cls

    def unregister(self, name: str) -> None:
        self._states.pop(name, None)

    def create(self, name: str) -> State:
        state_cls = self._states.get(name)
        if not state_cls:
            raise state_not_found(name, self.names())
        return state_cls()

    def names(self) -> list[str]:
        return sorted(self._states.keys())


class InitialState(State):
    async def handle_message(self, message: Message, component: Any) -> Tuple[bool, State]:
        if message.get("type") == "start":
            return True, AwaitingConfirmation()
        return False, self


class AwaitingConfirmation(State):
    async def handle_message(self, message: Message, component: Any) -> Tuple[bool, State]:
        t = message.get("type")
        if t == "confirm" and message.get("content") == "confirmed":
            return True, ProcessingRequest()
        if t == "cancel":
            return True, InitialState()
        return False, self


class ProcessingRequest(State):
    async def handle_message(self, message: Message, component: Any) -> Tuple[bool, State]:
        t = message.get("type")
        if t == "complete":
            return True, InitialState()
        if t == "error":
            return True, ErrorHandling()
        return False, self


class ErrorHandling(State):
    async def handle_message(self, message: Message, component: Any) -> Tuple[bool, State]:
        if message.get("type") == "acknowledge":
            return True, InitialState()
        return False, self


DEFAULT_REGISTRY = StateRegistry()
DEFAULT_REGISTRY.register("InitialState", InitialState)
DEFAULT_REGISTRY.register("AwaitingConfirmation", AwaitingConfirmation)
DEFAULT_REGISTRY.register("ProcessingRequest", ProcessingRequest)
DEFAULT_REGISTRY.register("ErrorHandling", ErrorHandling)


@dataclass
class StateMachine:
    current_state: State
    registry: StateRegistry = DEFAULT_REGISTRY

    @classmethod
    def from_name(cls, state_name: str, registry: StateRegistry = DEFAULT_REGISTRY) -> "StateMachine":
        return cls(current_state=registry.create(state_name), registry=registry)

    async def handle_message(self, message: Message, component: Any) -> bool:
        proceed, new_state = await self.current_state.handle_message(message, component)
        if proceed:
            self.current_state = new_state
        return proceed
