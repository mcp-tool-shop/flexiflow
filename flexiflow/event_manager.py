from __future__ import annotations

import asyncio
import uuid
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, DefaultDict, Dict, List, Optional

Handler = Callable[[Any], Awaitable[None]]
FilterFn = Callable[[str, Any], bool]


@dataclass(frozen=True)
class SubscriptionHandle:
    """Opaque handle returned by subscribe(), used for unsubscribe()."""
    event_name: str
    subscription_id: str  # uuid string


@dataclass(frozen=True)
class Subscription:
    subscription_id: str
    priority: int
    component_name: str
    handler: Handler
    filter_fn: Optional[FilterFn] = None


class AsyncEventManager:
    """Async pub/sub bus with priorities, optional filters, and sequential/concurrent delivery."""

    def __init__(self, logger: Any = None) -> None:
        self._events: DefaultDict[str, List[Subscription]] = defaultdict(list)
        self._logger = logger
        # Reverse index to speed up component-wide unsubscribe
        self._by_component: Dict[str, List[SubscriptionHandle]] = defaultdict(list)

    async def subscribe(
        self,
        event_name: str,
        component_name: str,
        handler: Handler,
        priority: int = 3,
        filter_fn: Optional[FilterFn] = None,
    ) -> SubscriptionHandle:
        """
        Subscribe a handler to an event.

        Returns a SubscriptionHandle that can be passed to unsubscribe().
        """
        if not (1 <= priority <= 5):
            raise ValueError("priority must be an integer between 1 and 5")

        subscription_id = str(uuid.uuid4())
        sub = Subscription(
            subscription_id=subscription_id,
            priority=priority,
            component_name=component_name,
            handler=handler,
            filter_fn=filter_fn,
        )
        self._events[event_name].append(sub)

        handle = SubscriptionHandle(event_name=event_name, subscription_id=subscription_id)
        self._by_component[component_name].append(handle)
        return handle

    def unsubscribe(self, handle: SubscriptionHandle) -> bool:
        """
        Remove a subscription by handle.

        Returns True if something was removed, False otherwise.
        Safe to call multiple times (idempotent).
        """
        subs = self._events.get(handle.event_name)
        if not subs:
            return False

        before = len(subs)
        subs[:] = [s for s in subs if s.subscription_id != handle.subscription_id]
        removed = len(subs) != before

        # Clean up reverse index
        if removed:
            for comp, handles in list(self._by_component.items()):
                new_list = [h for h in handles if h != handle]
                if len(new_list) != len(handles):
                    self._by_component[comp] = new_list
                    if not new_list:
                        self._by_component.pop(comp, None)
                    break

        # Clean up empty event lists
        if not subs:
            self._events.pop(handle.event_name, None)

        return removed

    def unsubscribe_all(self, component_name: str) -> int:
        """
        Unsubscribe all handlers registered by a component.

        Returns the number of subscriptions removed.
        """
        handles = self._by_component.pop(component_name, [])
        count = 0
        for h in handles:
            if self.unsubscribe(h):
                count += 1
        return count

    async def publish(
        self,
        event_name: str,
        data: Any = None,
        *,
        delivery: str = "sequential",   # "sequential" | "concurrent"
        on_error: str = "continue",     # "continue" | "raise"
    ) -> None:
        """
        Publish an event to all subscribed handlers.

        Args:
            event_name: The event to publish
            data: Optional data payload
            delivery: "sequential" (default) or "concurrent"
            on_error: "continue" (default, log and proceed) or "raise" (propagate first exception)
        """
        if delivery not in ("sequential", "concurrent"):
            raise ValueError("delivery must be 'sequential' or 'concurrent'")
        if on_error not in ("continue", "raise"):
            raise ValueError("on_error must be 'continue' or 'raise'")

        subs = self._events.get(event_name, [])
        if not subs:
            return

        eligible = [s for s in subs if s.filter_fn is None or s.filter_fn(event_name, data)]
        ordered = sorted(eligible, key=lambda s: s.priority)

        if delivery == "concurrent":
            tasks = [asyncio.create_task(s.handler(data)) for s in ordered]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            if on_error == "raise":
                for r in results:
                    if isinstance(r, Exception):
                        raise r

            if self._logger:
                for r in results:
                    if isinstance(r, Exception):
                        self._logger.error("Error handling event %s: %s", event_name, r)
            return

        # sequential delivery
        for s in ordered:
            try:
                await s.handler(data)
            except Exception as e:
                if self._logger:
                    self._logger.error("Error handling event %s: %s", event_name, e)
                if on_error == "raise":
                    raise
