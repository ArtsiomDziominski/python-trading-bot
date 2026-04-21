import asyncio
import logging

from sqlalchemy import select

from app.bot_engine.loop import run_bot
from app.db.session import async_session_factory
from app.models import Bot
from app.models.enums import BotLifecycleStatus

log = logging.getLogger(__name__)

_tasks: dict[int, asyncio.Task] = {}


async def supervisor_loop(poll_interval: float = 10.0) -> None:
    while True:
        try:
            async with async_session_factory() as s:
                result = await s.execute(
                    select(Bot.id).where(
                        Bot.lifecycle_status == BotLifecycleStatus.ACTIVE,
                        Bot.deleted_at.is_(None),
                    )
                )
                ids = [r[0] for r in result.all()]
            for bid in ids:
                if bid not in _tasks or _tasks[bid].done():
                    log.info("start bot task %s", bid)
                    _tasks[bid] = asyncio.create_task(run_bot(bid))
            for bid in list(_tasks.keys()):
                if bid not in ids and not _tasks[bid].done():
                    _tasks[bid].cancel()
                    log.info("cancel bot task %s", bid)
        except Exception:
            log.exception("supervisor tick failed")
        await asyncio.sleep(poll_interval)
