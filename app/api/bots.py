from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.openapi import OPENAPI_RESPONSES_PROTECTED
from app.db.session import get_db
from app.models import User
from app.models.enums import BotLifecycleStatus
from app.schemas.bot import BotCreate, BotEventOut, BotOut, BotPatch
from app.services import audit_service, bot_service

router = APIRouter(responses=OPENAPI_RESPONSES_PROTECTED)


@router.post(
    "",
    response_model=BotOut,
    summary="Создать бота",
    description="Создаёт конфигурацию сеточного бота для Binance Futures (лимиты по роли пользователя).",
)
async def create_bot(
    body: BotCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    try:
        bot = await bot_service.create_bot(db, user, body)
        await audit_service.audit(
            db,
            actor_user_id=user.id,
            action="bot.create",
            entity_type="bot",
            entity_id=str(bot.id),
        )
        return bot
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.get(
    "/active",
    response_model=list[BotOut],
    summary="Активные боты",
    description="Список ботов пользователя в статусе **active**.",
)
async def active_bots(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    return await bot_service.list_bots(db, user.id, lifecycle=BotLifecycleStatus.ACTIVE)


@router.get(
    "/stopped",
    response_model=list[BotOut],
    summary="Остановленные боты",
    description="Список ботов в статусе **stopped**.",
)
async def stopped_bots(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    return await bot_service.list_bots(db, user.id, lifecycle=BotLifecycleStatus.STOPPED)


@router.patch(
    "/{bot_id}",
    response_model=BotOut,
    summary="Обновить конфиг бота",
    description="Частичное обновление JSON-конфига сетки (валидация на сервисе).",
)
async def patch_bot(
    bot_id: int,
    body: BotPatch,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    try:
        return await bot_service.update_bot_config(db, user, bot_id, body.config)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.get(
    "/history",
    response_model=list[BotEventOut],
    summary="История событий ботов",
    description="События по всем ботам пользователя; при указании `bot_id` — фильтр по одному боту.",
)
async def bots_history(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    bot_id: int | None = Query(default=None),
):
    return await bot_service.bot_history(db, user.id, bot_id=bot_id)


@router.post(
    "/{bot_id}/stop",
    response_model=BotOut,
    summary="Остановить бота",
    description="Переводит бота в остановленное состояние без полного закрытия позиций (см. также **close**).",
)
async def stop_bot(
    bot_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    try:
        return await bot_service.stop_bot(db, user, bot_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.post(
    "/{bot_id}/close",
    response_model=BotOut,
    summary="Закрыть бота",
    description="Завершает работу бота и связанную логику закрытия (см. реализацию сервиса).",
)
async def close_bot(
    bot_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    try:
        return await bot_service.close_bot(db, user, bot_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
