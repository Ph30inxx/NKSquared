from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Valuation(Base):
    """Round-by-round valuation history for a portfolio company. Sprint 3 builds CRUD on top."""

    __tablename__ = "valuations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("portfolio_companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    valuation_date: Mapped[date] = mapped_column(Date, nullable=False)
    post_money_valuation_cr: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    pre_money_valuation_cr: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    currency: Mapped[str] = mapped_column(
        String(10), nullable=False, default="INR", server_default="INR"
    )

    # 'SSA','409A','Internal','Secondary','Audit'
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("idx_valuations_company_date", "company_id", "valuation_date"),
    )
