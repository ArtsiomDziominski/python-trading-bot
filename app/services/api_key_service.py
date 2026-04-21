from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import decrypt_secret, encrypt_secret
from app.core.rbac import max_api_keys_for_role
from app.models import ApiKey, User
from app.models.enums import ExchangeType


def mask_key(k: str) -> str:
    if len(k) <= 8:
        return "****"
    return k[:4] + "****" + k[-4:]


async def count_active_keys(db: AsyncSession, user_id: int) -> int:
    result = await db.execute(
        select(func.count()).select_from(ApiKey).where(ApiKey.user_id == user_id, ApiKey.deleted_at.is_(None))
    )
    return int(result.scalar_one())


async def create_api_key(
    db: AsyncSession,
    user: User,
    *,
    exchange: ExchangeType,
    api_key: str,
    api_secret: str,
    label: str,
) -> ApiKey:
    if exchange != ExchangeType.BINANCE:
        raise ValueError("Only BINANCE supported in MVP")
    limit = max_api_keys_for_role(user.role)
    n = await count_active_keys(db, user.id)
    if n >= limit:
        raise ValueError("API key limit reached for your role")
    row = ApiKey(
        user_id=user.id,
        exchange=exchange,
        label=label,
        api_key_enc=encrypt_secret(api_key),
        api_secret_enc=encrypt_secret(api_secret),
    )
    db.add(row)
    await db.flush()
    return row


async def list_api_keys(db: AsyncSession, user_id: int) -> list[ApiKey]:
    result = await db.execute(
        select(ApiKey).where(ApiKey.user_id == user_id, ApiKey.deleted_at.is_(None)).order_by(ApiKey.id)
    )
    return list(result.scalars().all())


async def soft_delete_api_key(db: AsyncSession, user_id: int, key_id: int) -> bool:
    from datetime import datetime, timezone

    result = await db.execute(select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == user_id))
    row = result.scalar_one_or_none()
    if row is None or row.deleted_at is not None:
        return False
    row.deleted_at = datetime.now(timezone.utc)
    return True


def masked_api_key(row: ApiKey) -> str:
    try:
        plain = decrypt_secret(row.api_key_enc)
    except Exception:
        return "****"
    return mask_key(plain)
