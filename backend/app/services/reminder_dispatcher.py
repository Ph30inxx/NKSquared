from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.company import PortfolioCompany
from app.models.mis import MisSubmission
from app.models.reminder import ReminderLog, ReminderSchedule
from app.services import email_service
from app.services.upload_token import make_upload_token

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates" / "email"
_jinja = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "j2"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


@dataclass(frozen=True)
class ReminderDecision:
    send: bool
    is_escalation: bool
    reason: str
    period: tuple[int, int]


def compute_expected_period(today: date) -> tuple[int, int]:
    """Previous calendar month — doc §7.1: on April 30 expected period is March."""
    if today.month == 1:
        return (today.year - 1, 12)
    return (today.year, today.month - 1)


def _period_label(year: int, month: int) -> str:
    return f"{date(year, month, 1):%b %Y}"


def _related_period_key(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


def _is_submission_done(db: Session, company_code: str, year: int, month: int) -> bool:
    sub = db.execute(
        select(MisSubmission).where(
            MisSubmission.company_id == company_code,
            MisSubmission.period_year == year,
            MisSubmission.period_month == month,
        )
    ).scalar_one_or_none()
    if sub is None:
        return False
    return sub.status == "Approved"


def _logs_for_period(
    db: Session, schedule_id: int, period_key: str
) -> list[ReminderLog]:
    rows = db.execute(
        select(ReminderLog)
        .where(
            ReminderLog.schedule_id == schedule_id,
            ReminderLog.related_period == period_key,
            ReminderLog.status != "Failed",
        )
        .order_by(ReminderLog.sent_at.desc())
    ).scalars().all()
    return list(rows)


def should_send_reminder(
    db: Session,
    schedule: ReminderSchedule,
    company: PortfolioCompany,
    today: date,
) -> ReminderDecision:
    period = compute_expected_period(today)
    period_key = _related_period_key(*period)

    if not schedule.enabled:
        return ReminderDecision(False, False, "schedule disabled", period)

    if company.company_code and _is_submission_done(db, company.company_code, *period):
        return ReminderDecision(False, False, "submission already approved", period)

    logs = _logs_for_period(db, schedule.id, period_key)
    sent_count = len(logs)

    # Period start = first day of the month FOLLOWING the reporting month.
    # e.g. for March data, the reporting window opens April 1.
    period_open = (
        date(period[0] + (1 if period[1] == 12 else 0), 1 if period[1] == 12 else period[1] + 1, 1)
    )

    if sent_count == 0:
        days_into_window = (today - period_open).days
        if days_into_window < schedule.first_reminder_offset_days:
            return ReminderDecision(False, False, "before first-reminder offset", period)
        return ReminderDecision(True, False, "first reminder", period)

    last_sent = logs[0].sent_at
    if last_sent.tzinfo is None:
        last_sent = last_sent.replace(tzinfo=timezone.utc)
    days_since = (datetime.now(timezone.utc) - last_sent).days
    if days_since < schedule.cadence_days:
        return ReminderDecision(False, False, "within cadence window", period)

    is_escalation = (sent_count + 1) >= schedule.escalation_threshold
    reason = "escalation due" if is_escalation else "cadence elapsed"
    return ReminderDecision(True, is_escalation, reason, period)


def _render_template(name: str, ctx: dict) -> tuple[str, str]:
    """Returns (subject, html_body). Subject is the first non-blank line, prefixed by `Subject:`."""
    template = _jinja.get_template(name)
    rendered = template.render(**ctx)
    lines = rendered.splitlines()
    subject = ""
    body_start = 0
    for i, line in enumerate(lines):
        if line.lower().startswith("subject:"):
            subject = line.split(":", 1)[1].strip()
            body_start = i + 1
            break
    html_body = "\n".join(lines[body_start:]).strip()
    return subject, html_body


def _first_name(full: str | None) -> str:
    if not full:
        return "there"
    return full.strip().split()[0] or "there"


def dispatch_reminder(
    db: Session,
    schedule: ReminderSchedule,
    is_escalation: bool,
    today: date | None = None,
) -> ReminderLog:
    today = today or datetime.now(timezone.utc).date()
    period = compute_expected_period(today)
    period_key = _related_period_key(*period)

    company = db.get(PortfolioCompany, schedule.company_id)
    if company is None:
        raise ValueError(f"company {schedule.company_id} not found")

    recipient = company.primary_contact_email
    if not recipient:
        raise ValueError(f"company {schedule.company_id} has no primary_contact_email")

    token = make_upload_token(company.id, period)
    portal_url = f"{settings.PUBLIC_UPLOAD_BASE_URL.rstrip('/')}/upload/{token}"

    ctx = {
        "company_name": company.company_name,
        "company_contact_first_name": _first_name(company.primary_contact_name),
        "period": _period_label(*period),
        "portal_url": portal_url,
        "analyst_name": settings.EMAIL_FROM_NAME,
        "analyst_email": settings.EMAIL_FROM,
        "fund_name": settings.FUND_NAME,
    }

    template_name = "escalation.html.j2" if is_escalation else "first_reminder.html.j2"
    subject, body_html = _render_template(template_name, ctx)

    cc: list[str] | None = None
    to_email = recipient
    to_name = company.primary_contact_name
    if is_escalation and company.escalation_contact_email:
        to_email = company.escalation_contact_email
        to_name = None
        cc = [recipient]

    log = ReminderLog(
        schedule_id=schedule.id,
        company_id=company.id,
        channel="Email",
        recipient_email=to_email,
        subject=subject,
        is_escalation=is_escalation,
        related_period=period_key,
        status="Sent",
    )
    try:
        email_service.send_email(
            to_email=to_email,
            to_name=to_name,
            subject=subject,
            body_html=body_html,
            cc=cc,
        )
    except Exception as exc:
        log.status = "Failed"
        log.subject = f"{subject} (error: {exc.__class__.__name__})"

    db.add(log)
    db.flush()
    db.commit()
    db.refresh(log)
    return log
