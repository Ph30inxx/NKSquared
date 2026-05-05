from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

_JSON = JSON().with_variant(JSONB(), "postgresql")


class MisSubmission(Base):
    __tablename__ = "mis_submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Internal company code (e.g. 'company_01') — intentionally not an FK to
    # portfolio_companies.id; matches the chatbot's MIS Agent expectations.
    company_id: Mapped[str] = mapped_column(String(20), nullable=False)
    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    period_month: Mapped[int] = mapped_column(Integer, nullable=False)
    fiscal_year: Mapped[str] = mapped_column(String(10), nullable=False)

    # 'Pending','Submitted','Under Review','Approved','Rejected','Resubmission Required'
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="Pending", server_default="Pending"
    )

    source_file_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    source_file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    uploaded_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    anomaly_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    template_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("mis_templates.id", ondelete="SET NULL"), nullable=True
    )
    last_parse_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_parse_payload: Mapped[dict | None] = mapped_column(_JSON, nullable=True)

    __table_args__ = (
        UniqueConstraint("company_id", "period_year", "period_month", name="uq_mis_submission_period"),
        Index(
            "idx_mis_submissions_status_period",
            "status",
            "period_year",
            "period_month",
        ),
    )


class MisMonthly(Base):
    __tablename__ = "mis_monthly"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    month_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    fiscal_year: Mapped[str | None] = mapped_column(String(10), nullable=True)
    quarter: Mapped[str | None] = mapped_column(String(5), nullable=True)
    geography: Mapped[str | None] = mapped_column(String(30), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)

    revenue_lacs: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    indirect_income_lacs: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    total_income_lacs: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    cogs_lacs: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    gross_margin_lacs: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    gross_margin_pct: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)
    total_operating_costs_lacs: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    manpower_cost_lacs: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    rent_lacs: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    utilities_lacs: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    electricity_lacs: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    channel_expenses_lacs: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    commission_lacs: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    transport_lacs: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    marketing_lacs: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    admin_lacs: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    it_lacs: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    professional_fees_lacs: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    compliance_costs_lacs: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    events_lacs: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    ebitda_lacs: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    ebitda_pct: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)
    itc_reversal_lacs: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    ebitda_with_itc_lacs: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)

    submission_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("mis_submissions.id", ondelete="CASCADE"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("company_id", "month_date", "geography", name="uq_mis_monthly_period_geo"),
        Index("idx_mis_monthly_company_date", "company_id", "month_date"),
    )


class MisBuMonthly(Base):
    __tablename__ = "mis_bu_monthly"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    bu_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    month_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    fiscal_year: Mapped[str | None] = mapped_column(String(10), nullable=True)
    quarter: Mapped[str | None] = mapped_column(String(5), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)

    revenue_lacs: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    cogs_lacs: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    gross_margin_lacs: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    gross_margin_pct: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)
    operating_costs_lacs: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    ebitda_lacs: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    ebitda_pct: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)

    channel_dine_in_lacs: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    channel_aggregator_a_lacs: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    channel_aggregator_b_lacs: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    channel_aggregator_d_lacs: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    channel_catering_lacs: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    channel_franchise_lacs: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)

    submission_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("mis_submissions.id", ondelete="CASCADE"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("company_id", "bu_id", "month_date", name="uq_mis_bu_monthly_period"),
    )


class MisAnomaly(Base):
    __tablename__ = "mis_anomalies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    submission_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("mis_submissions.id", ondelete="CASCADE"), nullable=False
    )
    rule_code: Mapped[str] = mapped_column(String(40), nullable=False)
    severity: Mapped[str] = mapped_column(String(10), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    metric: Mapped[str | None] = mapped_column(String(40), nullable=True)
    period_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    period_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    geography: Mapped[str | None] = mapped_column(String(30), nullable=True)
    bu_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("idx_mis_anomalies_submission", "submission_id"),
    )


class MisOutletMonthly(Base):
    __tablename__ = "mis_outlet_monthly"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    bu_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    outlet_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    city: Mapped[str | None] = mapped_column(String(30), nullable=True)
    month_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    area_sqft: Mapped[int | None] = mapped_column(Integer, nullable=True)
    covers: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sales_to_rent_ratio: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    revenue_lacs: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    cogs_lacs: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    gross_margin_lacs: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    gross_margin_pct: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)
    operating_costs_lacs: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    operational_profit_lacs: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    operational_profit_pct: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)

    submission_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("mis_submissions.id", ondelete="CASCADE"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
