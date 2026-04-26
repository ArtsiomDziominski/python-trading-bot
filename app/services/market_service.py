import json
from decimal import Decimal

import ccxt.async_support as ccxt_async
import httpx

from app.core.config import get_settings
from app.core.redis_client import get_redis
from app.exchanges.utils import ccxt_binance_usdm_demo_api_urls, to_ccxt_binance_futures


async def load_markets_unified() -> tuple[ccxt_async.binance, dict]:
    s = get_settings()
    opts: dict = {"options": {"defaultType": "future"}, "enableRateLimit": True}
    if s.binance_testnet:
        opts["urls"] = {"api": ccxt_binance_usdm_demo_api_urls()}
    ex = ccxt_async.binance(opts)
    await ex.load_markets()
    return ex, ex.markets


async def all_binance_futures_symbols() -> list[str]:
    r = get_redis()
    cache_key = "market:binance:futures:symbols"
    cached = await r.get(cache_key)
    if cached:
        return json.loads(cached)
    ex, markets = await load_markets_unified()
    try:
        symbols = sorted({m["symbol"] for m in markets.values() if m.get("future") or m.get("swap")})
    finally:
        await ex.close()
    await r.set(cache_key, json.dumps(symbols), ex=3600)
    return symbols


async def fetch_last_price(symbol: str) -> Decimal:
    s = get_settings()
    base_url = "https://demo-fapi.binance.com" if s.binance_testnet else "https://fapi.binance.com"
    url = f"{base_url}/fapi/v1/ticker/price"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url, params={"symbol": symbol.strip().upper()})
            response.raise_for_status()
            ticker = response.json()
    except httpx.HTTPError as e:
        raise ValueError(f"Could not fetch last price: {e}") from e
    last = ticker.get("price")
    if last is None:
        raise ValueError("Could not fetch last price")
    return Decimal(str(last))


async def resolve_user_symbols(user_symbols: list[str]) -> list[str]:
    """Return unified ccxt symbols that exist on the exchange for user's bot symbols (e.g. BTCUSDT)."""
    if not user_symbols:
        return []
    all_syms = await all_binance_futures_symbols()
    avail = set(all_syms)
    out: list[str] = []
    for us in user_symbols:
        try:
            u = to_ccxt_binance_futures(us)
        except ValueError:
            continue
        if u in avail:
            out.append(u)
    return sorted(set(out))
