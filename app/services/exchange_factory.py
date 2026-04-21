from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.encryption import decrypt_secret
from app.core.exchange_rate_limit import ExchangeCallGate
from app.core.redis_client import get_redis
from app.exchanges.binance import BinanceFuturesAdapter
from app.models import ApiKey


async def build_binance_adapter(
    db: AsyncSession,
    *,
    user_id: int,
    api_key_id: int,
) -> BinanceFuturesAdapter:
    result = await db.execute(select(ApiKey).where(ApiKey.id == api_key_id, ApiKey.user_id == user_id))
    row = result.scalar_one_or_none()
    if row is None or row.deleted_at is not None:
        raise ValueError("API key not found")
    get_settings()
    key = decrypt_secret(row.api_key_enc)
    secret = decrypt_secret(row.api_secret_enc)
    r = get_redis()
    gate = ExchangeCallGate(r)
    return BinanceFuturesAdapter(key, secret, api_key_id=api_key_id, gate=gate)
