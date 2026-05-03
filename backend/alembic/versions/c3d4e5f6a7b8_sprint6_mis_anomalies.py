"""sprint 6: mis_anomalies + portfolio_companies.company_code

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-05-03 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mis_anomalies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("submission_id", sa.Integer(), nullable=False),
        sa.Column("rule_code", sa.String(length=40), nullable=False),
        sa.Column("severity", sa.String(length=10), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("metric", sa.String(length=40), nullable=True),
        sa.Column("period_year", sa.Integer(), nullable=True),
        sa.Column("period_month", sa.Integer(), nullable=True),
        sa.Column("geography", sa.String(length=30), nullable=True),
        sa.Column("bu_id", sa.String(length=20), nullable=True),
        sa.Column(
            "detected_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["submission_id"], ["mis_submissions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_mis_anomalies_submission",
        "mis_anomalies",
        ["submission_id"],
        unique=False,
    )

    op.add_column(
        "portfolio_companies",
        sa.Column("company_code", sa.String(length=20), nullable=True),
    )
    op.create_index(
        "uq_portfolio_companies_code",
        "portfolio_companies",
        ["company_code"],
        unique=True,
        postgresql_where=sa.text("company_code IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_portfolio_companies_code", table_name="portfolio_companies")
    op.drop_column("portfolio_companies", "company_code")
    op.drop_index("idx_mis_anomalies_submission", table_name="mis_anomalies")
    op.drop_table("mis_anomalies")
