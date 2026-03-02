from __future__ import annotations

from typing import Any, Awaitable, Callable


class HealingLayer:
    async def run_with_healing(
        self,
        action: Callable[[], Awaitable[Any]],
        reload_state: Callable[[], Awaitable[None]],
        relearn: Callable[[], Awaitable[None]],
    ) -> Any:
        try:
            return await action()
        except Exception:
            await reload_state()
            await relearn()
            return await action()
