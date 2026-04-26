from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from ccxt.base.errors import AuthenticationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import max_active_bots_for_role
from app.exchanges.types import PositionSide as ExPositionSide
from app.models import ApiKey, Bot, BotEvent, Order, PositionSnapshot, User
from app.models.enums import BotLifecycleStatus, BotType, EngineState, OrderSide, OrderStatus, OrderType, PositionSide
from app.schemas.bot import BotCreate, GridFuturesConfig
from app.services import audit_service, events_bus
from app.services.exchange_factory import build_binance_adapter
from app.services.notification_service import notify_telegram_if_enabled
from app.bot_engine.loop import exchange_bootstrap_for_bot
from app.strategies.grid import close_position_order_id

log = logging.getLogger(__name__)

_BINANCE_AUTH_HINT = (
    "Binance rejected the API key (e.g. -2008 Invalid Api-Key ID). "
    "Use a valid USDT-M Futures key and set BINANCE_TESTNET to match the key "
    "(false for binance.com, true for testnet keys only)."
)


async def count_active_bots(db: AsyncSession, user_id: int) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(Bot)
        .where(Bot.user_id == user_id, Bot.lifecycle_status == BotLifecycleStatus.ACTIVE, Bot.deleted_at.is_(None))
    )
    return int(result.scalar_one())


async def create_bot(db: AsyncSession, user: User, body: BotCreate) -> Bot:
    user_id = user.id
    if body.bot_type != BotType.GRID_FUTURES:
        raise ValueError("Unsupported bot type")
    limit = max_active_bots_for_role(user.role)
    if await count_active_bots(db, user_id) >= limit:
        raise ValueError("Active bot limit reached")
    cfg: GridFuturesConfig = body.config
    result = await db.execute(
        select(ApiKey).where(
            ApiKey.id == body.api_key_id,
            ApiKey.user_id == user_id,
            ApiKey.deleted_at.is_(None),
        )
    )
    ak = result.scalar_one_or_none()
    if ak is None:
        raise ValueError("API key not found")
    bot = Bot(
        user_id=user_id,
        api_key_id=ak.id,
        bot_type=body.bot_type,
        symbol=cfg.symbol.upper(),
        lifecycle_status=BotLifecycleStatus.ACTIVE,
        engine_state=EngineState.INIT,
        config=json.loads(cfg.model_dump_json()),
        config_version=1,
    )
    db.add(bot)
    await db.flush()
    snap = PositionSnapshot(
        bot_id=bot.id,
        symbol=bot.symbol,
        side=PositionSide.LONG if cfg.direction.value == "LONG" else PositionSide.SHORT,
        size=Decimal("0"),
        entry_price=None,
    )
    db.add(snap)
    db.add(BotEvent(bot_id=bot.id, event_type="created", payload={"config_version": bot.config_version}))
    try:
        await exchange_bootstrap_for_bot(db, bot, user_id=user_id)
    except Exception as e:
        bot.engine_state = EngineState.ERROR
        bot.engine_error = str(e)[:2000]
        db.add(BotEvent(bot_id=bot.id, event_type="error", payload={"message": str(e)}))
    await db.refresh(bot)
    await events_bus.publish_user(
        user_id,
        "bots",
        {
            "event": "bot_created",
            "bot_id": bot.id,
            "exchange_ok": bot.engine_state != EngineState.ERROR,
        },
    )
    u = await db.get(User, user_id)
    if u is not None:
        msg = f"Бот #{bot.id} создан ({bot.symbol}, GRID_FUTURES)."
        if bot.engine_state == EngineState.ERROR:
            msg += " Ошибка выставления на бирже — см. engine_error в API."
        notify_telegram_if_enabled(u, msg)
    return bot


async def list_bots(
    db: AsyncSession,
    user_id: int,
    *,
    lifecycle: BotLifecycleStatus | None = None,
) -> list[Bot]:
    q = select(Bot).where(Bot.user_id == user_id, Bot.deleted_at.is_(None))
    if lifecycle is not None:
        q = q.where(Bot.lifecycle_status == lifecycle)
    q = q.order_by(Bot.id.desc())
    result = await db.execute(q)
    return list(result.scalars().all())


async def get_bot(db: AsyncSession, user_id: int, bot_id: int) -> Bot | None:
    result = await db.execute(
        select(Bot).where(Bot.id == bot_id, Bot.user_id == user_id, Bot.deleted_at.is_(None))
    )
    return result.scalar_one_or_none()


async def bot_history(db: AsyncSession, user_id: int, bot_id: int | None = None) -> list[BotEvent]:
    q = select(BotEvent).join(Bot).where(Bot.user_id == user_id)
    if bot_id is not None:
        q = q.where(BotEvent.bot_id == bot_id)
    q = q.order_by(BotEvent.id.desc()).limit(500)
    result = await db.execute(q)
    return list(result.scalars().all())


async def stop_bot(db: AsyncSession, user_id: int, bot_id: int) -> Bot:
    bot = await get_bot(db, user_id, bot_id)
    if bot is None:
        raise ValueError("Bot not found")
    if bot.lifecycle_status != BotLifecycleStatus.ACTIVE:
        raise ValueError("Bot is not active")
    adapter = await build_binance_adapter(db, user_id=user_id, api_key_id=bot.api_key_id)
    try:
        try:
            await adapter.cancel_all_orders(bot.symbol)
        except AuthenticationError as e:
            raise ValueError(_BINANCE_AUTH_HINT) from e
    finally:
        await adapter.close()
    bot.lifecycle_status = BotLifecycleStatus.STOPPED
    bot.engine_state = EngineState.STOPPED
    db.add(BotEvent(bot_id=bot.id, event_type="stopped", payload={}))
    await events_bus.publish_user(user_id, "bots", {"event": "bot_stopped", "bot_id": bot.id})
    u = await db.get(User, user_id)
    if u is not None:
        notify_telegram_if_enabled(u, f"Бот #{bot.id} остановлен ({bot.symbol}).")
    return bot


async def stop_all_active_bots(db: AsyncSession, user_id: int) -> tuple[list[Bot], list[tuple[int, str]]]:
    """Stop every ACTIVE bot for the user; commits after each success so partial progress survives later failures."""
    res = await db.execute(
        select(Bot.id)
        .where(
            Bot.user_id == user_id,
            Bot.deleted_at.is_(None),
            Bot.lifecycle_status == BotLifecycleStatus.ACTIVE,
        )
        .order_by(Bot.id.asc())
    )
    bot_ids: list[int] = list(res.scalars().all())
    stopped: list[Bot] = []
    failed: list[tuple[int, str]] = []
    for bot_id in bot_ids:
        try:
            bot = await stop_bot(db, user_id, bot_id)
            stopped.append(bot)
            await db.commit()
            await db.refresh(bot)
        except ValueError as e:
            await db.rollback()
            failed.append((bot_id, str(e)))
    return stopped, failed


async def close_bot(db: AsyncSession, user_id: int, bot_id: int) -> Bot:
    bot = await get_bot(db, user_id, bot_id)
    if bot is None:
        raise ValueError("Bot not found")
    if bot.lifecycle_status == BotLifecycleStatus.CLOSED:
        raise ValueError("Already closed")
    adapter = await build_binance_adapter(db, user_id=user_id, api_key_id=bot.api_key_id)
    try:
        try:
            await adapter.cancel_all_orders(bot.symbol)
            positions = await adapter.get_positions(bot.symbol)
            for p in positions:
                if p.size == 0:
                    continue
                side = OrderSide.SELL if p.side == ExPositionSide.LONG else OrderSide.BUY
                cid = close_position_order_id(bot.id, bot.config_version)
                await adapter.place_order(
                    bot.symbol,
                    side,
                    OrderType.MARKET,
                    p.size,
                    reduce_only=True,
                    client_order_id=cid,
                )
        except AuthenticationError as e:
            raise ValueError(_BINANCE_AUTH_HINT) from e
    finally:
        await adapter.close()
    bot.lifecycle_status = BotLifecycleStatus.CLOSED
    bot.engine_state = EngineState.STOPPED
    db.add(
        BotEvent(
            bot_id=bot.id,
            event_type="close_completed",
            payload={"lifecycle": BotLifecycleStatus.CLOSED.value},
        )
    )
    await events_bus.publish_user(user_id, "bots", {"event": "bot_closed", "bot_id": bot.id})
    u = await db.get(User, user_id)
    if u is not None:
        notify_telegram_if_enabled(u, f"Бот #{bot.id} закрыт ({bot.symbol}).")
    return bot


async def close_all_non_closed_bots(db: AsyncSession, user_id: int) -> tuple[list[Bot], list[tuple[int, str]]]:
    """Close every bot that is not CLOSED (active or stopped); commits after each success."""
    res = await db.execute(
        select(Bot.id)
        .where(
            Bot.user_id == user_id,
            Bot.deleted_at.is_(None),
            Bot.lifecycle_status != BotLifecycleStatus.CLOSED,
        )
        .order_by(Bot.id.asc())
    )
    bot_ids: list[int] = list(res.scalars().all())
    closed: list[Bot] = []
    failed: list[tuple[int, str]] = []
    for bot_id in bot_ids:
        try:
            bot = await close_bot(db, user_id, bot_id)
            closed.append(bot)
            await db.commit()
            await db.refresh(bot)
        except ValueError as e:
            await db.rollback()
            failed.append((bot_id, str(e)))
    return closed, failed


async def soft_delete_bot(db: AsyncSession, user_id: int, bot_id: int, *, notify: bool = True) -> Bot:
    """Hide bot from lists (`deleted_at`); keeps DB row. If ACTIVE, cancels open orders on the exchange first."""
    bot = await get_bot(db, user_id, bot_id)
    if bot is None:
        raise ValueError("Bot not found")
    if bot.lifecycle_status == BotLifecycleStatus.ACTIVE:
        adapter = await build_binance_adapter(db, user_id=user_id, api_key_id=bot.api_key_id)
        try:
            try:
                await adapter.cancel_all_orders(bot.symbol)
            except AuthenticationError as e:
                log.warning("soft_delete bot %s: exchange cancel skipped (%s)", bot.id, e)
        finally:
            await adapter.close()
        bot.lifecycle_status = BotLifecycleStatus.STOPPED
        bot.engine_state = EngineState.STOPPED
    bot.deleted_at = datetime.now(timezone.utc)
    db.add(BotEvent(bot_id=bot.id, event_type="removed_from_tracking", payload={}))
    await events_bus.publish_user(user_id, "bots", {"event": "bot_removed", "bot_id": bot.id})
    u = await db.get(User, user_id)
    if notify and u is not None:
        notify_telegram_if_enabled(u, f"Бот #{bot.id} убран из списка (данные в БД сохранены).")
    return bot


async def soft_delete_all_bots(db: AsyncSession, user_id: int) -> tuple[list[Bot], list[tuple[int, str]]]:
    """Soft-delete every bot for the user that is not already hidden; commits after each success."""
    res = await db.execute(
        select(Bot.id)
        .where(Bot.user_id == user_id, Bot.deleted_at.is_(None))
        .order_by(Bot.id.asc())
    )
    bot_ids: list[int] = list(res.scalars().all())
    removed: list[Bot] = []
    failed: list[tuple[int, str]] = []
    for bot_id in bot_ids:
        try:
            bot = await soft_delete_bot(db, user_id, bot_id, notify=False)
            removed.append(bot)
            await db.commit()
            await db.refresh(bot)
        except ValueError as e:
            await db.rollback()
            failed.append((bot_id, str(e)))
    u = await db.get(User, user_id)
    if u is not None and (removed or failed):
        notify_telegram_if_enabled(
            u,
            f"Массовое снятие с отслеживания: убрано {len(removed)}, ошибок {len(failed)}.",
        )
    return removed, failed


async def update_bot_config(db: AsyncSession, user: User, bot_id: int, cfg: GridFuturesConfig) -> Bot:
    bot = await get_bot(db, user.id, bot_id)
    if bot is None:
        raise ValueError("Bot not found")
    if bot.lifecycle_status == BotLifecycleStatus.CLOSED:
        raise ValueError("Cannot update a closed bot")
    bot.config = json.loads(cfg.model_dump_json())
    bot.config_version += 1
    bot.symbol = cfg.symbol.upper()
    res = await db.execute(select(PositionSnapshot).where(PositionSnapshot.bot_id == bot.id).limit(1))
    snap = res.scalar_one_or_none()
    if snap:
        snap.symbol = bot.symbol
        snap.side = PositionSide.LONG if cfg.direction.value == "LONG" else PositionSide.SHORT
    db.add(
        BotEvent(
            bot_id=bot.id,
            event_type="config_updated",
            payload={"config_version": bot.config_version},
        )
    )
    await audit_service.audit(
        db,
        actor_user_id=user.id,
        action="bot.config_update",
        entity_type="bot",
        entity_id=str(bot.id),
        payload={"config_version": bot.config_version},
    )
    await events_bus.publish_user(user.id, "bots", {"event": "bot_config_updated", "bot_id": bot.id})
    notify_telegram_if_enabled(user, f"Бот #{bot.id}: конфиг обновлён, версия {bot.config_version}.")
    return bot


async def symbols_for_user(db: AsyncSession, user_id: int) -> list[str]:
    result = await db.execute(
        select(Bot.symbol)
        .where(
            Bot.user_id == user_id,
            Bot.deleted_at.is_(None),
            Bot.lifecycle_status != BotLifecycleStatus.CLOSED,
        )
        .distinct()
    )
    return [r[0] for r in result.all()]
