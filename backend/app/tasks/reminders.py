import logging
from datetime import datetime, timezone

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.company import PortfolioCompany
from app.models.reminder import ReminderSchedule
from app.services import reminder_dispatcher
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.reminders.check_pending_mis")
def check_pending_mis() -> dict:
    """Hourly sweep — enqueues a send_reminder per schedule that is due."""
    today = datetime.now(timezone.utc).date()
    enqueued = 0
    skipped = 0
    db = SessionLocal()
    try:
        rows = db.execute(
            select(ReminderSchedule, PortfolioCompany)
            .join(PortfolioCompany, PortfolioCompany.id == ReminderSchedule.company_id)
            .where(
                ReminderSchedule.enabled.is_(True),
                PortfolioCompany.is_active.is_(True),
                PortfolioCompany.reporting_frequency == "Monthly",
            )
        ).all()
        for schedule, company in rows:
            decision = reminder_dispatcher.should_send_reminder(db, schedule, company, today)
            if not decision.send:
                skipped += 1
                continue
            send_reminder.delay(schedule.id, decision.is_escalation)
            enqueued += 1
    finally:
        db.close()
    logger.info("check_pending_mis: enqueued=%s skipped=%s", enqueued, skipped)
    return {"enqueued": enqueued, "skipped": skipped}


@celery_app.task(name="app.tasks.reminders.send_reminder")
def send_reminder(schedule_id: int, is_escalation: bool) -> int | None:
    db = SessionLocal()
    try:
        schedule = db.get(ReminderSchedule, schedule_id)
        if schedule is None:
            logger.warning("send_reminder: schedule %s missing", schedule_id)
            return None
        log = reminder_dispatcher.dispatch_reminder(db, schedule, is_escalation)
        return log.id
    finally:
        db.close()
