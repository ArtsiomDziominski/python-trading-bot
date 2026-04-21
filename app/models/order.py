from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, Enum as SAEnum, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import OrderSide, OrderStatus, OrderType

if TYPE_CHECKING:
    from app.models.bot import Bot


class Order(Base, TimestampMixin):
    __tablename__ = "orders"
    __table_args__ = (UniqueConstraint("client_order_id", name="uq_orders_client_order_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    bot_id: Mapped[int] = mapped_column(ForeignKey("bots.id", ondelete="CASCADE"), index=True)
    symbol: Mapped[str] = mapped_column(String(64), index=True)
    client_order_id: Mapped[str] = mapped_column(String(128), index=True)
    exchange_order_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    side: Mapped[OrderSide] = mapped_column(
        SAEnum(OrderSide, values_callable=lambda x: [e.value for e in x], name="orderside"),
    )
    type: Mapped[OrderType] = mapped_column(
        SAEnum(OrderType, values_callable=lambda x: [e.value for e in x], name="ordertype"),
    )
    status: Mapped[OrderStatus] = mapped_column(
        SAEnum(OrderStatus, values_callable=lambda x: [e.value for e in x], name="orderstatus"),
        default=OrderStatus.NEW,
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(38, 18))
    filled_quantity: Mapped[Decimal] = mapped_column(Numeric(38, 18), default=Decimal("0"))
    avg_price: Mapped[Decimal | None] = mapped_column(Numeric(38, 18), nullable=True)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    bot: Mapped["Bot"] = relationship(back_populates="orders")
