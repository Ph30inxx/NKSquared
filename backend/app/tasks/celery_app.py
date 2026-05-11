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
            # Intraday refresh; row is per-day so each call overwrites today's quote.
            "schedule": crontab(minute=0, hour=f"*/{settings.FX_REFRESH_HOURS}"),
        },
        "check_pending_mis": {
            "task": "app.tasks.reminders.check_pending_mis",
            "schedule": crontab(minute=0),
        },
        "refresh_portfolio_aggregates": {
            "task": "app.tasks.aggregates.refresh_portfolio_aggregates",
            "schedule": crontab(minute="*/5"),
        },
    },
)

celery_app.autodiscover_tasks(["app.tasks"])

# Explicit imports — autodiscover looks for `<pkg>/tasks.py`, not modules inside
# `app.tasks/`, so we have to register our task modules by hand.
from app.tasks import fx_loader  # noqa: E402, F401
from app.tasks import reminders  # noqa: E402, F401
from app.tasks import aggregates  # noqa: E402, F401
