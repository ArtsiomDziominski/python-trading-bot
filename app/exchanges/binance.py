from collections.abc import Awaitable, Callable
from decimal import Decimal
from typing import TypeVar

import ccxt.async_support as ccxt_async

from app.core.config import get_settings
from app.core.exchange_rate_limit import ExchangeCallGate
from app.exchanges.base import ExchangeAdapter
from app.exchanges.retry import retry_ccxt
from app.exchanges.types import BalanceSnapshot, OrderInfo, PlaceOrderResult, PositionInfo, PositionSide
from app.exchanges.utils import ccxt_binance_usdm_demo_api_urls, to_ccxt_binance_futures
from app.models.enums import OrderSide, OrderType

T = TypeVar("T")


def _ccxt_side(side: OrderSide) -> str:
    return "buy" if side == OrderSide.BUY else "sell"


def _map_position_side(raw: str) -> PositionSide:
    r = (raw or "").lower()
    if "short" in r or r == "sell":
        return PositionSide.SHORT
    return PositionSide.LONG


class BinanceFuturesAdapter(ExchangeAdapter):
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        *,
        api_key_id: int,
        gate: ExchangeCallGate | None = None,
    ) -> None:
        self._settings = get_settings()
        self._api_key_id = api_key_id
        self._gate = gate
        self._binance_time_synced = False
        self._dual_side_position: bool | None = None
        opts: dict = {
            "apiKey": api_key,
            "secret": api_secret,
            "enableRateLimit": True,
            "options": {
                "defaultType": "future",
                "adjustForTimeDifference": True,
                "recvWindow": 60_000,
            },
        }
        if self._settings.binance_testnet:
            opts["urls"] = {"api": ccxt_binance_usdm_demo_api_urls()}
        self._ex = ccxt_async.binance(opts)

    async def _sync_binance_time(self) -> None:
        if self._binance_time_synced:
            return
        await self._ex.load_time_difference()
        self._binance_time_synced = True

    async def _reload_binance_clock(self) -> None:
        self._binance_time_synced = False
        await self._ex.load_time_difference()
        self._binance_time_synced = True

    async def _ensure_dual_side_position(self, ccxt_symbol: str) -> None:
        if self._dual_side_position is not None:
            return
        pm = await self._retry_ccxt(lambda: self._ex.fetch_position_mode(ccxt_symbol))
        self._dual_side_position = bool(pm.get("hedged"))

    @staticmethod
    def _position_side_for_order(side: OrderSide, *, reduce_only: bool) -> str:
        if reduce_only:
            return "LONG" if side == OrderSide.SELL else "SHORT"
        return "LONG" if side == OrderSide.BUY else "SHORT"

    async def _retry_ccxt(self, call: Callable[[], Awaitable[T]]) -> T:
        return await retry_ccxt(call, resync_exchange_clock=self._reload_binance_clock)

    async def _maybe_limit(self) -> None:
        await self._sync_binance_time()
        if self._gate:
            await self._gate.acquire(self._api_key_id)

    async def place_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        amount: Decimal,
        *,
        price: Decimal | None = None,
        reduce_only: bool = False,
        client_order_id: str | None = None,
    ) -> PlaceOrderResult:
        await self._maybe_limit()
        ccxt_symbol = to_ccxt_binance_futures(symbol)
        params: dict = {}
        if client_order_id:
            params["newClientOrderId"] = client_order_id[:36]
        if reduce_only:
            params["reduceOnly"] = True
        await self._ensure_dual_side_position(ccxt_symbol)
        if self._dual_side_position:
            params["positionSide"] = self._position_side_for_order(side, reduce_only=reduce_only)
        if order_type == OrderType.MARKET:
            o = await self._retry_ccxt(
                lambda: self._ex.create_market_order(
                    ccxt_symbol, _ccxt_side(side), float(amount), params=params
                )
            )
        else:
            if price is None:
                raise ValueError("price required for limit order")
            o = await self._retry_ccxt(
                lambda: self._ex.create_limit_order(
                    ccxt_symbol, _ccxt_side(side), float(amount), float(price), params=params
                )
            )
        oid = str(o.get("id", ""))
        status = str(o.get("status", "new"))
        filled = Decimal(str(o.get("filled", 0) or 0))
        avg = o.get("average")
        return PlaceOrderResult(
            exchange_order_id=oid,
            client_order_id=client_order_id,
            status=status,
            filled=filled,
            average=Decimal(str(avg)) if avg is not None else None,
        )

    async def cancel_order(self, symbol: str, exchange_order_id: str) -> None:
        await self._maybe_limit()
        ccxt_symbol = to_ccxt_binance_futures(symbol)
        await self._retry_ccxt(lambda: self._ex.cancel_order(exchange_order_id, ccxt_symbol))

    async def cancel_all_orders(self, symbol: str) -> None:
        await self._maybe_limit()
        ccxt_symbol = to_ccxt_binance_futures(symbol)
        await self._retry_ccxt(lambda: self._ex.cancel_all_orders(ccxt_symbol))

    async def get_positions(self, symbol: str | None = None) -> list[PositionInfo]:
        await self._maybe_limit()
        syms = [to_ccxt_binance_futures(symbol)] if symbol else None
        positions = await self._retry_ccxt(lambda: self._ex.fetch_positions(symbols=syms))
        out: list[PositionInfo] = []
        for p in positions:
            contracts = p.get("contracts")
            if contracts is None:
                continue
            size = Decimal(str(contracts))
            if size == 0:
                continue
            side_raw = p.get("side") or ""
            out.append(
                PositionInfo(
                    symbol=str(p.get("symbol", symbol or "")),
                    side=_map_position_side(side_raw),
                    size=abs(size),
                    entry_price=Decimal(str(p["entryPrice"])) if p.get("entryPrice") else None,
                )
            )
        return out

    async def get_open_orders(self, symbol: str | None = None) -> list[OrderInfo]:
        await self._maybe_limit()
        ccxt_symbol = to_ccxt_binance_futures(symbol) if symbol else None
        orders = await self._retry_ccxt(lambda: self._ex.fetch_open_orders(ccxt_symbol))
        result: list[OrderInfo] = []
        for o in orders:
            side = OrderSide.BUY if o.get("side") == "buy" else OrderSide.SELL
            typ = OrderType.LIMIT if (o.get("type") or "").lower() == "limit" else OrderType.MARKET
            result.append(
                OrderInfo(
                    exchange_order_id=str(o["id"]),
                    client_order_id=o.get("clientOrderId"),
                    symbol=str(o.get("symbol", "")),
                    status=str(o.get("status", "")),
                    side=side,
                    type=typ,
                    amount=Decimal(str(o.get("amount", 0))),
                    filled=Decimal(str(o.get("filled", 0))),
                    average=Decimal(str(o["average"])) if o.get("average") else None,
                )
            )
        return result

    async def get_balance(self) -> list[BalanceSnapshot]:
        await self._maybe_limit()
        bal = await self._retry_ccxt(lambda: self._ex.fetch_balance())
        out: list[BalanceSnapshot] = []
        for cur, data in bal.items():
            if cur in ("free", "used", "total", "info"):
                continue
            if isinstance(data, dict) and "total" in data:
                out.append(
                    BalanceSnapshot(
                        currency=cur,
                        total=Decimal(str(data.get("total", 0))),
                        free=Decimal(str(data.get("free", 0))),
                    )
                )
        return out

    async def fetch_last_price(self, symbol: str) -> Decimal:
        await self._maybe_limit()
        ccxt_symbol = to_ccxt_binance_futures(symbol)
        t = await self._retry_ccxt(lambda: self._ex.fetch_ticker(ccxt_symbol))
        last = t.get("last") or t.get("close") or t.get("info", {}).get("lastPrice")
        return Decimal(str(last))

    async def close(self) -> None:
        await self._ex.close()
