from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ReminderSchedule(Base):
    __tablename__ = "reminder_schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("portfolio_companies.id"), nullable=False
    )

    # 'MIS_MONTHLY','MIS_QUARTERLY','VALUATION_REVIEW','CUSTOM'
    reminder_type: Mapped[str] = mapped_column(String(30), nullable=False)

    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    cadence_days: Mapped[int] = mapped_column(Integer, nullable=False, default=7, server_default="7")
    first_reminder_offset_days: Mapped[int] = mapped_column(
        Integer, nullable=False, default=5, server_default="5"
    )
    escalation_threshold: Mapped[int] = mapped_column(
        Integer, nullable=False, default=3, server_default="3"
    )
    escalation_contact_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    template_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class ReminderLog(Base):
    __tablename__ = "reminder_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    schedule_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("reminder_schedules.id"), nullable=True
    )
    company_id: Mapped[int] = mapped_column(Integer, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # 'Email','InApp','SMS'
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    recipient_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="Sent", server_default="Sent"
    )
    is_escalation: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    related_period: Mapped[str | None] = mapped_column(String(16), nullable=True)

    __table_args__ = (
        Index("idx_reminder_company_period", "company_id", "related_period"),
    )
