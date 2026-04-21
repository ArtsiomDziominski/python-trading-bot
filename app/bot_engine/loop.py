"""Polling-based bot loop (MVP): sync exchange → DB, idempotent grid placement, restart when flat."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory
from app.exchanges.types import PositionSide as ExPositionSide
from app.models import Bot, BotEvent, Order, PositionSnapshot, User
from app.models.enums import (
    BotLifecycleStatus,
    BotType,
    EngineState,
    OrderSide,
    OrderStatus,
    OrderType,
    PositionSide,
)
from app.schemas.bot import GridFuturesConfig
from app.services.exchange_factory import build_binance_adapter
from app.strategies.grid import GridLevelKind, client_order_id, grid_prices, level_size

log = logging.getLogger(__name__)

async def _sync_orders_and_position(s: AsyncSession, bot: Bot, adapter) -> None:
    symbol = bot.symbol
    open_o = await adapter.get_open_orders(symbol)
    for o in open_o:
        cid = (o.client_order_id or "").strip()
        if not cid:
            continue
        result = await s.execute(select(Order).where(Order.client_order_id == cid))
        row = result.scalar_one_or_none()
        st = (o.status or "").upper()
        if "CANCEL" in st:
            status = OrderStatus.CANCELED
        elif "PART" in st:
            status = OrderStatus.PARTIALLY_FILLED
        elif st in ("FILLED", "CLOSED"):
            status = OrderStatus.FILLED
        else:
            status = OrderStatus.NEW
        if row is None:
            s.add(
                Order(
                    bot_id=bot.id,
                    symbol=symbol,
                    client_order_id=cid,
                    exchange_order_id=o.exchange_order_id,
                    side=o.side,
                    type=o.type,
                    status=status,
                    quantity=o.amount,
                    filled_quantity=o.filled,
                    avg_price=o.average,
                )
            )
        else:
            row.status = status
            row.filled_quantity = o.filled
            row.exchange_order_id = o.exchange_order_id or row.exchange_order_id
            row.avg_price = o.average

    pos = await adapter.get_positions(symbol)
    snap_res = await s.execute(select(PositionSnapshot).where(PositionSnapshot.bot_id == bot.id).limit(1))
    snap = snap_res.scalar_one_or_none()
    if not pos:
        if snap:
            snap.size = Decimal("0")
            snap.entry_price = None
            snap.updated_at = datetime.now(timezone.utc)
        return
    p = pos[0]
    side = PositionSide.LONG if p.side == ExPositionSide.LONG else PositionSide.SHORT
    if snap is None:
        s.add(
            PositionSnapshot(
                bot_id=bot.id,
                symbol=symbol,
                side=side,
                size=p.size,
                entry_price=p.entry_price,
            )
        )
    else:
        snap.side = side
        snap.size = p.size
        snap.entry_price = p.entry_price
        snap.updated_at = datetime.now(timezone.utc)


async def _ensure_grid_once(s: AsyncSession, bot: Bot, adapter) -> None:
    if bot.bot_type != BotType.GRID_FUTURES:
        return
    cfg = GridFuturesConfig.model_validate(bot.config)

    async def row_for(cid: str) -> Order | None:
        return await s.scalar(select(Order).where(Order.client_order_id == cid))

    anchor = cfg.start_price or await adapter.fetch_last_price(cfg.symbol)
    eid = client_order_id(bot.id, bot.config_version, GridLevelKind.entry, 0)
    side = OrderSide.BUY if cfg.direction.value == "LONG" else OrderSide.SELL

    er = await row_for(eid)
    if er is None:
        s.add(
            Order(
                bot_id=bot.id,
                symbol=cfg.symbol,
                client_order_id=eid,
                exchange_order_id=None,
                side=side,
                type=OrderType.MARKET,
                status=OrderStatus.NEW,
                quantity=cfg.initial_amount,
                filled_quantity=Decimal("0"),
                avg_price=None,
            )
        )
        await s.flush()
        er = await row_for(eid)
    if er and not er.exchange_order_id:
        m = await adapter.place_order(
            cfg.symbol,
            side,
            OrderType.MARKET,
            cfg.initial_amount,
            client_order_id=eid,
        )
        er = await row_for(eid)
        if er:
            er.exchange_order_id = m.exchange_order_id
            er.status = (
                OrderStatus.FILLED if m.filled >= cfg.initial_amount * Decimal("0.99") else OrderStatus.PARTIALLY_FILLED
            )

    prices = grid_prices(
        anchor,
        direction=cfg.direction,
        grid_orders_count=cfg.grid_orders_count,
        grid_step_percent=cfg.grid_step_percent,
    )
    for i, price in enumerate(prices):
        oid = client_order_id(bot.id, bot.config_version, GridLevelKind.grid, i)
        qty = level_size(cfg.initial_amount, i, cfg.volume_mode)
        gr = await row_for(oid)
        if gr and gr.exchange_order_id:
            continue
        if gr is None:
            s.add(
                Order(
                    bot_id=bot.id,
                    symbol=cfg.symbol,
                    client_order_id=oid,
                    exchange_order_id=None,
                    side=side,
                    type=OrderType.LIMIT,
                    status=OrderStatus.NEW,
                    quantity=qty,
                    filled_quantity=Decimal("0"),
                    avg_price=None,
                )
            )
            await s.flush()
        r = await adapter.place_order(
            cfg.symbol,
            side,
            OrderType.LIMIT,
            qty,
            price=price,
            client_order_id=oid,
        )
        orow = await row_for(oid)
        if orow:
            orow.exchange_order_id = r.exchange_order_id


async def _maybe_restart(s: AsyncSession, bot: Bot, adapter) -> None:
    cfg = GridFuturesConfig.model_validate(bot.config)
    if not cfg.auto_restart:
        return
    pos = await adapter.get_positions(cfg.symbol)
    open_o = await adapter.get_open_orders(cfg.symbol)
    if pos or open_o:
        return
    n = await s.scalar(select(func.count()).select_from(Order).where(Order.bot_id == bot.id))
    if not n or int(n) == 0:
        return
    bot.engine_state = EngineState.RESTARTING
    await adapter.cancel_all_orders(cfg.symbol)
    await s.execute(delete(Order).where(Order.bot_id == bot.id))
    bot.config_version += 1
    bot.config = json.loads(cfg.model_dump_json())
    bot.engine_state = EngineState.RUNNING
    s.add(BotEvent(bot_id=bot.id, event_type="grid_recreated", payload={"config_version": bot.config_version}))


async def run_bot(bot_id: int) -> None:
    backoff = 1.0
    while True:
        try:
            async with async_session_factory() as s:
                bot = await s.get(Bot, bot_id)
                if bot is None or bot.deleted_at is not None:
                    return
                if bot.lifecycle_status != BotLifecycleStatus.ACTIVE:
                    return
                user = await s.get(User, bot.user_id)
                if user is None:
                    return
                adapter = await build_binance_adapter(s, user_id=user.id, api_key_id=bot.api_key_id)
                try:
                    if bot.engine_state == EngineState.INIT:
                        bot.engine_state = EngineState.RUNNING
                    await _sync_orders_and_position(s, bot, adapter)
                    await _maybe_restart(s, bot, adapter)
                    await _ensure_grid_once(s, bot, adapter)
                    bot.engine_error = None
                    await s.commit()
                finally:
                    await adapter.close()
                backoff = 1.0
        except Exception as e:
            log.exception("bot %s: %s", bot_id, e)
            try:
                async with async_session_factory() as serr:
                    b = await serr.get(Bot, bot_id)
                    if b:
                        b.engine_state = EngineState.ERROR
                        b.engine_error = str(e)[:2000]
                        serr.add(BotEvent(bot_id=b.id, event_type="error", payload={"message": str(e)}))
                        await serr.commit()
            except Exception:
                log.exception("persist error state failed")
            backoff = min(backoff * 2, 60.0)
        await asyncio.sleep(max(5.0, backoff))
