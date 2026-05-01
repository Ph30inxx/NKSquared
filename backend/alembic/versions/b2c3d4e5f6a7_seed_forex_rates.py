"""seed monthly forex rates for USD/AED/EUR -> INR

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-01 07:30:00.000000

"""
from datetime import date, timedelta
from decimal import Decimal
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Representative INR conversion factors used to populate the dev database.
# Real-world rates fluctuate; these are static demo values that let the MOIC and
# XIRR pipeline run end-to-end without an external feed (FX_PROVIDER='manual', § 8.3).
SEED_RATES = {
    "USD": Decimal("83.00"),
    "AED": Decimal("22.60"),
    "EUR": Decimal("89.50"),
}


def _monthly_dates(months_back: int = 24) -> list[date]:
    """First day of each of the past `months_back` months, oldest first."""
    today = date.today().replace(day=1)
    dates: list[date] = []
    cursor = today
    for _ in range(months_back):
        dates.append(cursor)
        # Step back one month.
        prev_last_day = cursor - timedelta(days=1)
        cursor = prev_last_day.replace(day=1)
    dates.reverse()
    return dates


def upgrade() -> None:
    forex_rates = sa.table(
        "forex_rates",
        sa.column("from_currency", sa.String),
        sa.column("to_currency", sa.String),
        sa.column("rate", sa.Numeric),
        sa.column("effective_date", sa.Date),
        sa.column("source", sa.String),
    )

    rows = []
    for d in _monthly_dates(24):
        for ccy, rate in SEED_RATES.items():
            rows.append(
                {
                    "from_currency": ccy,
                    "to_currency": "INR",
                    "rate": rate,
                    "effective_date": d,
                    "source": "seed",
                }
            )

    # The unique constraint is (effective_date, from_currency, to_currency); skip
    # any pair that already exists so the migration is safe to re-run.
    bind = op.get_bind()
    stmt = sa.text(
        """
        INSERT INTO forex_rates (from_currency, to_currency, rate, effective_date, source)
        VALUES (:from_currency, :to_currency, :rate, :effective_date, :source)
        ON CONFLICT (effective_date, from_currency, to_currency) DO NOTHING
        """
    )
    bind.execute(stmt, rows)


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM forex_rates WHERE source = 'seed' "
            "AND from_currency IN ('USD','AED','EUR') AND to_currency = 'INR'"
        )
    )
