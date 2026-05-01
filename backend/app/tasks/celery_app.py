from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery(
    "nksquared",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "fetch_daily_fx_rates": {
            "task": "app.tasks.fx_loader.fetch_daily_rates",
            # 06:00 UTC = ~11:30 IST, after RBI publishes the prior day's rates.
            "schedule": crontab(hour=6, minute=0),
        },
    },
)

celery_app.autodiscover_tasks(["app.tasks"])
