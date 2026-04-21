import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_otp_code
from app.models import TelegramLinkCode, User


async def create_link_code(db: AsyncSession, user_id: int) -> tuple[str, datetime]:
    raw = "".join(secrets.choice("0123456789") for _ in range(6))
    exp = datetime.now(timezone.utc) + timedelta(minutes=10)
    await db.execute(delete(TelegramLinkCode).where(TelegramLinkCode.user_id == user_id))
    db.add(
        TelegramLinkCode(
            user_id=user_id,
            code_hash=hash_otp_code(raw),
            expires_at=exp,
        )
    )
    await db.flush()
    return raw, exp


async def consume_link_code(db: AsyncSession, raw_code: str, telegram_user_id: str, chat_id: str) -> User | None:
    th = hash_otp_code(raw_code.strip())
    result = await db.execute(
        select(TelegramLinkCode).where(
            TelegramLinkCode.code_hash == th,
            TelegramLinkCode.consumed_at.is_(None),
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        return None
    if row.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        return None
    user = await db.get(User, row.user_id)
    if user is None:
        return None
    user.telegram_id = telegram_user_id
    user.telegram_chat_id = chat_id
    row.consumed_at = datetime.now(timezone.utc)
    return user
