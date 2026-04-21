from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import BigInteger, DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import BotLifecycleStatus, BotType, EngineState

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.api_key import ApiKey
    from app.models.order import Order
    from app.models.position import PositionSnapshot
    from app.models.events import BotEvent


class Bot(Base, TimestampMixin):
    __tablename__ = "bots"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    api_key_id: Mapped[int] = mapped_column(ForeignKey("api_keys.id", ondelete="RESTRICT"), index=True)
    bot_type: Mapped[BotType] = mapped_column(
        SAEnum(BotType, values_callable=lambda x: [e.value for e in x], name="bottype"),
    )
    symbol: Mapped[str] = mapped_column(String(64), index=True)
    lifecycle_status: Mapped[BotLifecycleStatus] = mapped_column(
        SAEnum(BotLifecycleStatus, values_callable=lambda x: [e.value for e in x], name="botlifecyclestatus"),
        default=BotLifecycleStatus.ACTIVE,
    )
    engine_state: Mapped[EngineState] = mapped_column(
        SAEnum(EngineState, values_callable=lambda x: [e.value for e in x], name="enginestate"),
        default=EngineState.INIT,
    )
    engine_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    config_version: Mapped[int] = mapped_column(Integer, default=1)
    deleted_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    user: Mapped["User"] = relationship(back_populates="bots")
    api_key: Mapped["ApiKey"] = relationship(back_populates="bots")
    orders: Mapped[list["Order"]] = relationship(back_populates="bot", lazy="selectin")
    position_snapshots: Mapped[list["PositionSnapshot"]] = relationship(back_populates="bot", lazy="selectin")
    events: Mapped[list["BotEvent"]] = relationship(back_populates="bot", lazy="selectin")
