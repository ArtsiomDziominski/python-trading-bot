import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

from ccxt.base.errors import DDoSProtection, ExchangeNotAvailable, NetworkError, RequestTimeout

log = logging.getLogger(__name__)

T = TypeVar("T")

_RETRYABLE = (NetworkError, ExchangeNotAvailable, DDoSProtection, RequestTimeout)


async def retry_ccxt(call: Callable[[], Awaitable[T]], *, attempts: int = 4, base_delay: float = 0.35) -> T:
    delay = base_delay
    for i in range(attempts):
        try:
            return await call()
        except _RETRYABLE as e:
            if i == attempts - 1:
                raise
            log.warning("ccxt retry %s/%s after %s", i + 1, attempts, e)
            await asyncio.sleep(delay)
            delay = min(delay * 2, 8.0)
