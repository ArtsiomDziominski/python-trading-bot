from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.openapi import OPENAPI_RESPONSES_PROTECTED
from app.db.session import get_db
from app.models import User
from app.schemas.user import (
    TelegramSendMessageRequest,
    TelegramSendMessageResponse,
    UserOut,
    UserUpdate,
)
from app.services import audit_service, telegram_link_service

router = APIRouter(responses=OPENAPI_RESPONSES_PROTECTED)


@router.get(
    "/me",
    response_model=UserOut,
    summary="Текущий пользователь",
    description="Профиль по действующему access token.",
)
async def me(user: Annotated[User, Depends(get_current_user)]):
    return user


@router.patch(
    "/update",
    response_model=UserOut,
    summary="Обновить профиль",
    description="Имя и флаги уведомлений Telegram; изменения пишутся в аудит.",
)
async def update_user(
    body: UserUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    if body.name is not None:
        user.name = body.name
    if body.telegram_notifications_enabled is not None:
        user.telegram_notifications_enabled = body.telegram_notifications_enabled
    await audit_service.audit(
        db,
        actor_user_id=user.id,
        action="user.update",
        entity_type="user",
        entity_id=str(user.id),
        payload=body.model_dump(exclude_unset=True),
    )
    return user


@router.post(
    "/telegram/link-code",
    summary="Код привязки Telegram",
    description="Одноразовый код и время истечения для привязки аккаунта к боту в Telegram.",
)
async def telegram_link_code(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    code, expires_at = await telegram_link_service.create_link_code(db, user.id)
    return {"code": code, "expires_at": expires_at}


@router.post(
    "/telegram/send",
    tags=["telegram"],
    response_model=TelegramSendMessageResponse,
    summary="Отправить сообщение в Telegram",
    description=(
        "Ставит в очередь отправку текста в привязанный чат (тот же бот, что и для уведомлений). "
        "Нужен `telegram_chat_id` после привязки аккаунта в боте и настроенный `TELEGRAM_BOT_TOKEN` на сервере."
    ),
)
async def telegram_send_message(
    body: TelegramSendMessageRequest,
    user: Annotated[User, Depends(get_current_user)],
):
    if not user.telegram_chat_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Telegram не привязан: сначала получите код в POST /user/telegram/link-code и введите его в боте.",
        )
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Telegram-бот на сервере не настроен (TELEGRAM_BOT_TOKEN).",
        )
    try:
        from app.workers.tasks import notify_telegram

        notify_telegram.delay(str(user.telegram_chat_id), body.message)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Не удалось поставить сообщение в очередь: {e!s}",
        ) from e
    return TelegramSendMessageResponse()
