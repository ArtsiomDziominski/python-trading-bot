from decimal import Decimal

import ccxt.async_support as ccxt_async

from app.core.config import get_settings
from app.core.exchange_rate_limit import ExchangeCallGate
from app.exchanges.base import ExchangeAdapter
from app.exchanges.retry import retry_ccxt
from app.exchanges.types import BalanceSnapshot, OrderInfo, PlaceOrderResult, PositionInfo, PositionSide
from app.exchanges.utils import to_ccxt_binance_futures
from app.models.enums import OrderSide, OrderType


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
        opts: dict = {
            "apiKey": api_key,
            "secret": api_secret,
            "enableRateLimit": True,
            "options": {"defaultType": "future"},
        }
        if self._settings.binance_testnet:
            opts["urls"] = {
                "api": {
                    "public": "https://testnet.binancefuture.com/fapi/v1",
                    "private": "https://testnet.binancefuture.com/fapi/v1",
                }
            }
        self._ex = ccxt_async.binance(opts)

    async def _maybe_limit(self) -> None:
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
        if order_type == OrderType.MARKET:
            o = await retry_ccxt(
                lambda: self._ex.create_market_order(
                    ccxt_symbol, _ccxt_side(side), float(amount), params=params
                )
            )
        else:
            if price is None:
                raise ValueError("price required for limit order")
            o = await retry_ccxt(
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
        await retry_ccxt(lambda: self._ex.cancel_order(exchange_order_id, ccxt_symbol))

    async def cancel_all_orders(self, symbol: str) -> None:
        await self._maybe_limit()
        ccxt_symbol = to_ccxt_binance_futures(symbol)
        await retry_ccxt(lambda: self._ex.cancel_all_orders(ccxt_symbol))

    async def get_positions(self, symbol: str | None = None) -> list[PositionInfo]:
        await self._maybe_limit()
        syms = [to_ccxt_binance_futures(symbol)] if symbol else None
        positions = await retry_ccxt(lambda: self._ex.fetch_positions(symbols=syms))
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
        orders = await retry_ccxt(lambda: self._ex.fetch_open_orders(ccxt_symbol))
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
        bal = await retry_ccxt(lambda: self._ex.fetch_balance())
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
        t = await retry_ccxt(lambda: self._ex.fetch_ticker(ccxt_symbol))
        last = t.get("last") or t.get("close") or t.get("info", {}).get("lastPrice")
        return Decimal(str(last))

    async def close(self) -> None:
        await self._ex.close()
