from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "trading_bot",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.task_routes = {"app.workers.tasks.*": {"queue": "default"}}

import app.workers.tasks  # noqa: E402, F401


@celery_app.task(name="ping")
def ping() -> str:
    return "pong"
