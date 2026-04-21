from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, Enum as SAEnum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import ExchangeType

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.bot import Bot


class ApiKey(Base, TimestampMixin):
    __tablename__ = "api_keys"
    __table_args__ = (UniqueConstraint("user_id", "label", name="uq_api_keys_user_label"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    exchange: Mapped[ExchangeType] = mapped_column(
        SAEnum(ExchangeType, values_callable=lambda x: [e.value for e in x], name="exchangetype"),
    )
    label: Mapped[str] = mapped_column(String(128), default="default")
    api_key_enc: Mapped[str] = mapped_column(String(1024))
    api_secret_enc: Mapped[str] = mapped_column(String(1024))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="api_keys")
    bots: Mapped[list["Bot"]] = relationship(back_populates="api_key")
