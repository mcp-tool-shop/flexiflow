from __future__ import annotations

import asyncio
from typing import Awaitable, Callable

try:
    from watchfiles import awatch
except ImportError:  # optional dependency
    awatch = None


async def watch_path(path: str, on_change: Callable[[], Awaitable[None]]) -> None:
    if awatch is None:
        raise RuntimeError("watchfiles is not installed. Install with: pip install -e '.[reload]'")
    async for _changes in awatch(path):
        await on_change()


def run_hot_reload(path: str, on_change: Callable[[], Awaitable[None]]) -> None:
    asyncio.run(watch_path(path, on_change))
