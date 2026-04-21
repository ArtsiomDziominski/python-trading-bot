from abc import ABC, abstractmethod
from decimal import Decimal

from app.exchanges.types import BalanceSnapshot, OrderInfo, PlaceOrderResult, PositionInfo
from app.models.enums import OrderSide, OrderType


class ExchangeAdapter(ABC):
    @abstractmethod
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
        raise NotImplementedError

    @abstractmethod
    async def cancel_order(self, symbol: str, exchange_order_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def cancel_all_orders(self, symbol: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_positions(self, symbol: str | None = None) -> list[PositionInfo]:
        raise NotImplementedError

    @abstractmethod
    async def get_open_orders(self, symbol: str | None = None) -> list[OrderInfo]:
        raise NotImplementedError

    @abstractmethod
    async def get_balance(self) -> list[BalanceSnapshot]:
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        """Release underlying HTTP session."""
        raise NotImplementedError
