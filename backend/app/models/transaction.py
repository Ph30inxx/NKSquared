from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PortfolioTransaction(Base):
    __tablename__ = "portfolio_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("portfolio_companies.id", ondelete="CASCADE"), nullable=False
    )
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)

    # 'Investment','Follow_on','Partial_exit','Full_exit','Distribution','Write_down','Write_off'
    transaction_type: Mapped[str] = mapped_column(String(30), nullable=False)

    amount_cr: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    original_currency: Mapped[str] = mapped_column(
        String(10), nullable=False, default="INR", server_default="INR"
    )
    original_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    amount_inr_cr: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    fx_rate_used: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)

    series: Mapped[str | None] = mapped_column(String(64), nullable=True)
    instrument_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    investing_entity: Mapped[str | None] = mapped_column(String(128), nullable=True)
    shares: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    share_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    pre_money_valuation_cr: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    post_money_valuation_cr: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    shareholding_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 6), nullable=True)
    ssa_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ssa_recorded_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("idx_portfolio_transactions_company_date", "company_id", "transaction_date"),
    )
