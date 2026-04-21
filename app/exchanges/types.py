from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from app.models.enums import OrderSide, OrderType


class PositionSide(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


@dataclass
class BalanceSnapshot:
    currency: str
    total: Decimal
    free: Decimal


@dataclass
class PositionInfo:
    symbol: str
    side: PositionSide
    size: Decimal
    entry_price: Decimal | None


@dataclass
class OrderInfo:
    exchange_order_id: str
    client_order_id: str | None
    symbol: str
    status: str
    side: OrderSide
    type: OrderType
    amount: Decimal
    filled: Decimal
    average: Decimal | None


@dataclass
class PlaceOrderResult:
    exchange_order_id: str
    client_order_id: str | None
    status: str
    filled: Decimal
    average: Decimal | None
