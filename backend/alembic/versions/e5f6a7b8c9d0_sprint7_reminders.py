"""sprint 7: portfolio_companies contact columns for reminders

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-05-04 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "portfolio_companies",
        sa.Column("primary_contact_name", sa.String(length=120), nullable=True),
    )
    op.add_column(
        "portfolio_companies",
        sa.Column("primary_contact_email", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "portfolio_companies",
        sa.Column("escalation_contact_email", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("portfolio_companies", "escalation_contact_email")
    op.drop_column("portfolio_companies", "primary_contact_email")
    op.drop_column("portfolio_companies", "primary_contact_name")
