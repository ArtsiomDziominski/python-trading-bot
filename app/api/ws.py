import logging
from typing import Annotated

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from jose import JWTError

from app.core.security import decode_token
from app.core.redis_client import get_redis

log = logging.getLogger(__name__)

router = APIRouter()


@router.websocket(
    "",
    name="user_events_ws",
)
async def websocket_endpoint(
    websocket: WebSocket,
    token: Annotated[
        str | None,
        Query(
            description="Тот же **access JWT**, что используется в заголовке `Authorization: Bearer ...` (в query передаётся только строка токена).",
        ),
    ] = None,
):
    if not token:
        await websocket.close(code=4401)
        return
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            await websocket.close(code=4401)
            return
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        await websocket.close(code=4401)
        return

    await websocket.accept()
    r = get_redis()
    pubsub = r.pubsub()
    await pubsub.psubscribe(f"user:{user_id}:*")

    async def forward():
        try:
            async for msg in pubsub.listen():
                if msg["type"] != "pmessage":
                    continue
                data = msg.get("data")
                if isinstance(data, bytes):
                    data = data.decode()
                await websocket.send_text(data)
        except WebSocketDisconnect:
            raise
        except Exception as e:
            log.warning("ws forward error: %s", e)

    try:
        await forward()
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.punsubscribe()
        await pubsub.close()
        try:
            await websocket.close()
        except Exception:
            pass
