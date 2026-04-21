"""Отправка уведомлений в Telegram через Celery (worker должен быть запущен)."""

import logging

from app.models import User

log = logging.getLogger(__name__)


def notify_telegram_if_enabled(user: User, text: str) -> None:
    if not user.telegram_chat_id or not user.telegram_notifications_enabled:
        return
    try:
        from app.workers.tasks import notify_telegram

        notify_telegram.delay(str(user.telegram_chat_id), text[:3500])
    except Exception as e:
        log.warning("telegram notify enqueue failed: %s", e)
