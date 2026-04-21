"""Rate limiting for outbound exchange calls per API key (Redis)."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import ParamSpec, TypeVar

import redis.asyncio as redis

from app.core.config import get_settings

P = ParamSpec("P")
T = TypeVar("T")


class ExchangeCallGate:
    def __init__(self, r: redis.Redis) -> None:
        self._r = r
        self._settings = get_settings()

    async def acquire(self, api_key_id: int, method: str = "default") -> None:
        key = f"rl:exch:{api_key_id}:{method}"
        limit = max(1, self._settings.exchange_rate_per_minute)
        while True:
            n = await self._r.incr(key)
            if n == 1:
                await self._r.expire(key, 60)
            if n <= limit:
                return
            await self._r.decr(key)
            await asyncio.sleep(0.05)


async def with_exchange_limit(
    gate: ExchangeCallGate,
    api_key_id: int,
    fn: Callable[P, Awaitable[T]],
    *args: P.args,
    **kwargs: P.kwargs,
) -> T:
    await gate.acquire(api_key_id)
    return await fn(*args, **kwargs)
