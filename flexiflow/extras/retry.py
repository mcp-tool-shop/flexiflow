"""Async retry decorator with exponential backoff."""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Type

AsyncFn = Callable[..., Awaitable[Any]]


@dataclass(frozen=True)
class RetryConfig:
    """Configuration for retry behavior.

    Attributes:
        max_attempts: Maximum number of attempts (must be >= 1)
        base_delay: Initial delay between retries in seconds
        max_delay: Maximum delay cap in seconds
        backoff: Multiplier applied to delay after each retry
        jitter: Random jitter as fraction of delay (0.0 to 1.0)
        retry_on: Tuple of exception types to retry on
    """

    max_attempts: int = 3
    base_delay: float = 0.1
    max_delay: float = 2.0
    backoff: float = 2.0
    jitter: float = 0.0
    retry_on: tuple[Type[BaseException], ...] = (Exception,)


def retry_async(config: RetryConfig) -> Callable[[AsyncFn], AsyncFn]:
    """Decorator that retries an async function with exponential backoff.

    Example:
        @retry_async(RetryConfig(max_attempts=3, base_delay=0.2))
        async def flaky_handler(data):
            ...
    """
    if config.max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")
    if config.base_delay < 0 or config.max_delay < 0:
        raise ValueError("delays must be >= 0")
    if config.backoff < 1.0:
        raise ValueError("backoff must be >= 1.0")
    if not (0.0 <= config.jitter <= 1.0):
        raise ValueError("jitter must be between 0.0 and 1.0")

    def decorator(fn: AsyncFn) -> AsyncFn:
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            attempt = 0
            delay = config.base_delay

            while True:
                attempt += 1
                try:
                    return await fn(*args, **kwargs)
                except config.retry_on:
                    if attempt >= config.max_attempts:
                        raise

                    if delay > 0:
                        # Apply jitter as a fraction of delay
                        if config.jitter:
                            jitter_amt = delay * config.jitter * random.random()
                        else:
                            jitter_amt = 0.0

                        await asyncio.sleep(min(config.max_delay, delay + jitter_amt))

                    delay = min(config.max_delay, delay * config.backoff)

        return wrapper  # type: ignore[return-value]

    return decorator
