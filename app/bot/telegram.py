import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command
from aiogram.types import Message

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.db.session import async_session_factory
from app.services.telegram_link_service import consume_link_code

log = logging.getLogger(__name__)
router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    await message.answer("Send the 6-digit code from the web app (User → Telegram link code).")


@router.message()
async def on_text(message: Message) -> None:
    if not message.text:
        return
    raw = message.text.strip()
    if len(raw) != 6 or not raw.isdigit():
        await message.answer("Expected a 6-digit numeric code.")
        return
    tid = str(message.from_user.id) if message.from_user else ""
    chat = str(message.chat.id)
    async with async_session_factory() as s:
        user = await consume_link_code(s, raw, tid, chat)
        await s.commit()
    if user is None:
        await message.answer("Invalid or expired code.")
        return
    await message.answer("Linked successfully. Notifications enabled for your account.")


async def main() -> None:
    setup_logging()
    settings = get_settings()
    if not settings.telegram_bot_token:
        log.error("TELEGRAM_BOT_TOKEN is not set")
        sys.exit(1)
    bot = Bot(settings.telegram_bot_token)
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
