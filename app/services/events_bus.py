import json
import logging

from app.core.redis_client import get_redis

log = logging.getLogger(__name__)


async def publish_user(user_id: int, channel: str, payload: dict) -> None:
    try:
        r = get_redis()
        await r.publish(f"user:{user_id}:{channel}", json.dumps(payload, default=str))
    except Exception as e:
        log.warning("redis publish failed: %s", e)
