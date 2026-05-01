from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, Index, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PortfolioCompany(Base):
    __tablename__ = "portfolio_companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_name: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # 'Entity_D_Core','Entity_D_Non_Core','Entity_D_LLC','Entity_E',
    # 'Entity_A','Strategic_Equity','Entity_C','Real_Estate_Debt'
    portfolio_type: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # 'Active','Written_off','Exit_via_IPO','Exit_via_Share_swap','Matured'
    investment_status: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # 'Unrealized','Realized'
    portfolio_status: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # 'Direct_Equity','Fund_Investment','Debt_Instrument'
    asset_class: Mapped[str | None] = mapped_column(String(30), nullable=True)

    sector: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sub_sector: Mapped[str | None] = mapped_column(String(80), nullable=True)
    country: Mapped[str | None] = mapped_column(String(50), nullable=True)
    date_of_first_investment: Mapped[date | None] = mapped_column(Date, nullable=True)

    # NEGATIVE = cash outflow. Always wrap in ABS() at display time.
    investment_value_cr: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    current_value_cr: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    moic: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    irr: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="INR", server_default="INR")

    primary_contact_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reporting_frequency: Mapped[str] = mapped_column(
        String(20), nullable=False, default="Monthly", server_default="Monthly"
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("idx_portfolio_sector", "sector"),
        Index("idx_portfolio_status", "portfolio_status", "investment_status"),
        Index("idx_portfolio_type", "portfolio_type"),
    )
