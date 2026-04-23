from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.openapi import OPENAPI_RESPONSES_PROTECTED
from app.db.session import get_db
from app.models import User
from app.models.enums import BotLifecycleStatus
from app.schemas.bot import (
    BotCreate,
    BotEventOut,
    BotOut,
    BotPatch,
    BotsCloseAllResponse,
    BotsRemoveAllResponse,
    BotsStopAllResponse,
    BotStopAllFailure,
)
from app.services import audit_service, bot_service

router = APIRouter(responses=OPENAPI_RESPONSES_PROTECTED)


@router.post(
    "",
    response_model=BotOut,
    summary="Создать бота",
    description="Создаёт бота и сразу пытается выставить сетку на Binance (как первый тик движка). При ошибке биржи **`engine_state`** будет **ERROR**, текст — в **`engine_error`**; запись в БД всё равно сохраняется.",
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


@router.post(
    "/stop-all",
    response_model=BotsStopAllResponse,
    summary="Остановить всех активных ботов",
    description="Для каждого бота в статусе **active** снимает ордера на бирже и переводит в **stopped**; успешные остановки фиксируются в БД до следующего бота.",
)
async def stop_all_bots(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    user_id = user.id
    stopped, failed_pairs = await bot_service.stop_all_active_bots(db, user_id)
    if stopped:
        await audit_service.audit(
            db,
            actor_user_id=user_id,
            action="bot.stop_all",
            entity_type="bot",
            entity_id="batch",
            payload={
                "stopped_ids": [b.id for b in stopped],
                "stopped_count": len(stopped),
                "failed_count": len(failed_pairs),
            },
        )
    return BotsStopAllResponse(
        stopped=stopped,
        failed=[BotStopAllFailure(bot_id=i, detail=d) for i, d in failed_pairs],
    )


@router.post(
    "/close-all",
    response_model=BotsCloseAllResponse,
    summary="Закрыть всех незакрытых ботов",
    description="Для каждого бота не в статусе **closed** (в т.ч. **stopped**): снимает ордера, закрывает позицию рынком, переводит в **closed**; успех фиксируется в БД до следующего бота.",
)
async def close_all_bots(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    user_id = user.id
    closed, failed_pairs = await bot_service.close_all_non_closed_bots(db, user_id)
    if closed:
        await audit_service.audit(
            db,
            actor_user_id=user_id,
            action="bot.close_all",
            entity_type="bot",
            entity_id="batch",
            payload={
                "closed_ids": [b.id for b in closed],
                "closed_count": len(closed),
                "failed_count": len(failed_pairs),
            },
        )
    return BotsCloseAllResponse(
        closed=closed,
        failed=[BotStopAllFailure(bot_id=i, detail=d) for i, d in failed_pairs],
    )


@router.post(
    "/remove-all",
    response_model=BotsRemoveAllResponse,
    summary="Убрать всех ботов из отслеживания",
    description="Для каждого бота без **`deleted_at`**: мягкое удаление (как **DELETE /bots/{id}**), в т.ч. если Binance отклонил ключ при снятии ордеров. Успех фиксируется в БД до следующего.",
)
async def remove_all_bots_from_tracking(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    user_id = user.id
    removed, failed_pairs = await bot_service.soft_delete_all_bots(db, user_id)
    if removed:
        await audit_service.audit(
            db,
            actor_user_id=user_id,
            action="bot.remove_all",
            entity_type="bot",
            entity_id="batch",
            payload={
                "removed_ids": [b.id for b in removed],
                "removed_count": len(removed),
                "failed_count": len(failed_pairs),
            },
        )
    return BotsRemoveAllResponse(
        removed=removed,
        failed=[BotStopAllFailure(bot_id=i, detail=d) for i, d in failed_pairs],
    )


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
        return await bot_service.stop_bot(db, user.id, bot_id)
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
        return await bot_service.close_bot(db, user.id, bot_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.delete(
    "/{bot_id}",
    response_model=BotOut,
    summary="Убрать бота из отслеживания",
    description="Не удаляет строку в БД: выставляет **`deleted_at`**, бот пропадает из списков. Для **active** пытается снять ордера на Binance; при ошибке ключа (-2008 и т.п.) снятие пропускается, но скрытие в приложении всё равно выполняется.",
)
async def remove_bot_from_tracking(
    bot_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    user_id = user.id
    try:
        bot = await bot_service.soft_delete_bot(db, user_id, bot_id)
        await audit_service.audit(
            db,
            actor_user_id=user_id,
            action="bot.soft_delete",
            entity_type="bot",
            entity_id=str(bot_id),
        )
        return bot
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
