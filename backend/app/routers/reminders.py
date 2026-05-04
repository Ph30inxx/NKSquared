from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_role
from app.db.session import get_db
from app.models.company import PortfolioCompany
from app.models.reminder import ReminderLog, ReminderSchedule
from app.models.user import User
from app.schemas.reminder import (
    PaginatedReminderLogs,
    ReminderLogResponse,
    ReminderScheduleCreate,
    ReminderScheduleResponse,
    ReminderScheduleUpdate,
    SendNowRequest,
)
from app.services import reminder_dispatcher

router = APIRouter(prefix="/reminders", tags=["reminders"])

_writer = require_role(["ADMIN", "ANALYST"])


def _get_schedule_or_404(db: Session, schedule_id: int) -> ReminderSchedule:
    row = db.get(ReminderSchedule, schedule_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return row


@router.get("/schedules", response_model=list[ReminderScheduleResponse])
def list_schedules(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    company_id: int | None = None,
) -> list[ReminderSchedule]:
    stmt = select(ReminderSchedule).order_by(ReminderSchedule.id.desc())
    if company_id is not None:
        stmt = stmt.where(ReminderSchedule.company_id == company_id)
    return list(db.execute(stmt).scalars().all())


@router.post(
    "/schedules",
    response_model=ReminderScheduleResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_schedule(
    payload: ReminderScheduleCreate,
    db: Session = Depends(get_db),
    _user: User = Depends(_writer),
) -> ReminderSchedule:
    if db.get(PortfolioCompany, payload.company_id) is None:
        raise HTTPException(status_code=400, detail="company_id does not exist")
    row = ReminderSchedule(**payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.patch("/schedules/{schedule_id}", response_model=ReminderScheduleResponse)
def update_schedule(
    schedule_id: int,
    payload: ReminderScheduleUpdate,
    db: Session = Depends(get_db),
    _user: User = Depends(_writer),
) -> ReminderSchedule:
    row = _get_schedule_or_404(db, schedule_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/schedules/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(_writer),
) -> None:
    row = _get_schedule_or_404(db, schedule_id)
    db.delete(row)
    db.commit()


@router.get("/logs", response_model=PaginatedReminderLogs)
def list_logs(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    company_id: int | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> PaginatedReminderLogs:
    base = select(ReminderLog)
    if company_id is not None:
        base = base.where(ReminderLog.company_id == company_id)
    total = db.execute(select(func.count()).select_from(base.subquery())).scalar_one()
    items = (
        db.execute(base.order_by(ReminderLog.sent_at.desc()).limit(limit).offset(offset))
        .scalars()
        .all()
    )
    return PaginatedReminderLogs(
        total=total,
        limit=limit,
        offset=offset,
        items=[ReminderLogResponse.model_validate(r) for r in items],
    )


@router.post(
    "/companies/{company_id}/send-now",
    response_model=ReminderLogResponse,
)
def send_now(
    company_id: int,
    payload: SendNowRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(_writer),
) -> ReminderLog:
    company = db.get(PortfolioCompany, company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    schedule = db.execute(
        select(ReminderSchedule)
        .where(ReminderSchedule.company_id == company_id)
        .order_by(ReminderSchedule.id.desc())
    ).scalars().first()
    if schedule is None:
        raise HTTPException(
            status_code=400,
            detail="Company has no reminder schedule configured",
        )
    if not company.primary_contact_email:
        raise HTTPException(
            status_code=400,
            detail="Company has no primary_contact_email set",
        )
    today = datetime.now(timezone.utc).date()
    return reminder_dispatcher.dispatch_reminder(
        db, schedule, payload.is_escalation, today=today
    )
