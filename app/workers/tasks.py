import logging

import httpx

from app.core.config import get_settings
from app.workers.celery_app import celery_app

log = logging.getLogger(__name__)


@celery_app.task(name="notify_telegram")
def notify_telegram(chat_id: str, text: str) -> None:
    s = get_settings()
    if not s.telegram_bot_token or not chat_id:
        log.warning("telegram notify skipped: missing token or chat_id")
        return
    url = f"https://api.telegram.org/bot{s.telegram_bot_token}/sendMessage"
    try:
        httpx.post(url, json={"chat_id": chat_id, "text": text}, timeout=15.0)
    except Exception as e:
        log.warning("telegram send failed: %s", e)


@celery_app.task(name="notify_user_event")
def notify_user_event(user_id: int, event: str, payload: dict) -> None:
    """Placeholder: enqueue Telegram from DB user settings (sync DB access omitted for brevity)."""
    log.info("notify_user_event user=%s event=%s payload=%s", user_id, event, payload)
