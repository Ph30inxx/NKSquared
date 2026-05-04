from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from app.models.company import PortfolioCompany
from app.models.mis import MisSubmission
from app.models.reminder import ReminderLog, ReminderSchedule
from app.services import reminder_dispatcher
from app.services.reminder_dispatcher import compute_expected_period, should_send_reminder


def _company(db: Session, **overrides) -> PortfolioCompany:
    defaults = dict(
        company_name="Acme",
        company_code="company_99",
        is_active=True,
        reporting_frequency="Monthly",
        primary_contact_email="ops@acme.example",
        primary_contact_name="Ada Lovelace",
        currency="INR",
    )
    defaults.update(overrides)
    c = PortfolioCompany(**defaults)
    db.add(c)
    db.flush()
    return c


def _schedule(db: Session, company: PortfolioCompany, **overrides) -> ReminderSchedule:
    defaults = dict(
        company_id=company.id,
        reminder_type="MIS_MONTHLY",
        enabled=True,
        cadence_days=7,
        first_reminder_offset_days=5,
        escalation_threshold=3,
    )
    defaults.update(overrides)
    s = ReminderSchedule(**defaults)
    db.add(s)
    db.flush()
    return s


def _log(db: Session, schedule: ReminderSchedule, *, days_ago: int, period: tuple[int, int],
         status: str = "Sent", is_escalation: bool = False) -> ReminderLog:
    sent_at = datetime.now(timezone.utc) - timedelta(days=days_ago)
    row = ReminderLog(
        schedule_id=schedule.id,
        company_id=schedule.company_id,
        sent_at=sent_at,
        channel="Email",
        recipient_email="ops@acme.example",
        subject="r",
        status=status,
        is_escalation=is_escalation,
        related_period=f"{period[0]:04d}-{period[1]:02d}",
    )
    db.add(row)
    db.flush()
    return row


def test_compute_expected_period_january_wraps_to_december_prior_year() -> None:
    assert compute_expected_period(date(2026, 1, 15)) == (2025, 12)


def test_compute_expected_period_general_case() -> None:
    assert compute_expected_period(date(2026, 5, 4)) == (2026, 4)


def test_skips_when_already_approved(db: Session) -> None:
    today = date(2026, 5, 30)
    company = _company(db)
    schedule = _schedule(db, company)
    db.add(MisSubmission(
        company_id=company.company_code,
        period_year=2026,
        period_month=4,
        fiscal_year="FY27",
        status="Approved",
    ))
    db.flush()
    decision = should_send_reminder(db, schedule, company, today)
    assert decision.send is False
    assert "approved" in decision.reason


def test_first_reminder_blocked_before_offset(db: Session) -> None:
    company = _company(db)
    schedule = _schedule(db, company, first_reminder_offset_days=10)
    today = date(2026, 5, 3)  # window opened May 1 → 2 days in
    decision = should_send_reminder(db, schedule, company, today)
    assert decision.send is False


def test_first_reminder_fires_after_offset(db: Session) -> None:
    company = _company(db)
    schedule = _schedule(db, company, first_reminder_offset_days=2)
    today = date(2026, 5, 5)  # 4 days into May → past offset
    decision = should_send_reminder(db, schedule, company, today)
    assert decision.send is True
    assert decision.is_escalation is False


def test_within_cadence_window_skipped(db: Session) -> None:
    company = _company(db)
    schedule = _schedule(db, company, cadence_days=7)
    today = date(2026, 5, 10)
    _log(db, schedule, days_ago=2, period=(2026, 4))
    decision = should_send_reminder(db, schedule, company, today)
    assert decision.send is False


def test_cadence_elapsed_triggers_send(db: Session) -> None:
    company = _company(db)
    schedule = _schedule(db, company, cadence_days=7, escalation_threshold=10)
    today = date(2026, 5, 20)
    _log(db, schedule, days_ago=8, period=(2026, 4))
    decision = should_send_reminder(db, schedule, company, today)
    assert decision.send is True
    assert decision.is_escalation is False


def test_escalation_after_threshold(db: Session) -> None:
    company = _company(db)
    schedule = _schedule(db, company, cadence_days=7, escalation_threshold=3)
    today = date(2026, 5, 30)
    _log(db, schedule, days_ago=20, period=(2026, 4))
    _log(db, schedule, days_ago=12, period=(2026, 4))
    decision = should_send_reminder(db, schedule, company, today)
    assert decision.send is True
    assert decision.is_escalation is True


def test_dispatch_reminder_records_failure_when_smtp_blows_up(db: Session, monkeypatch) -> None:
    company = _company(db)
    schedule = _schedule(db, company)

    def boom(**_kwargs):
        raise OSError("connection refused")

    monkeypatch.setattr(reminder_dispatcher.email_service, "send_email", boom)
    log = reminder_dispatcher.dispatch_reminder(db, schedule, is_escalation=False, today=date(2026, 5, 30))
    assert log.status == "Failed"
    assert log.is_escalation is False
    assert log.related_period == "2026-04"


def test_dispatch_reminder_records_sent_on_success(db: Session, monkeypatch) -> None:
    company = _company(db)
    schedule = _schedule(db, company)
    captured = {}

    def fake_send(**kwargs):
        captured.update(kwargs)
        return "<id@nksquared>"

    monkeypatch.setattr(reminder_dispatcher.email_service, "send_email", fake_send)
    log = reminder_dispatcher.dispatch_reminder(db, schedule, is_escalation=False, today=date(2026, 5, 30))
    assert log.status == "Sent"
    assert captured["to_email"] == "ops@acme.example"
    assert "/upload/" in captured["body_html"]
