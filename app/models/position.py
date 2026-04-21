from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, Enum as SAEnum, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import PositionSide

if TYPE_CHECKING:
    from app.models.bot import Bot


class PositionSnapshot(Base, TimestampMixin):
    __tablename__ = "position_snapshots"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    bot_id: Mapped[int] = mapped_column(ForeignKey("bots.id", ondelete="CASCADE"), index=True)
    symbol: Mapped[str] = mapped_column(String(64), index=True)
    side: Mapped[PositionSide] = mapped_column(
        SAEnum(PositionSide, values_callable=lambda x: [e.value for e in x], name="positionside"),
    )
    size: Mapped[Decimal] = mapped_column(Numeric(38, 18), default=Decimal("0"))
    entry_price: Mapped[Decimal | None] = mapped_column(Numeric(38, 18), nullable=True)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    bot: Mapped["Bot"] = relationship(back_populates="position_snapshots")
