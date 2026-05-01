"""sprint 1: portfolio_categories and valuations

Revision ID: a1b2c3d4e5f6
Revises: 22285d36f29a
Create Date: 2026-05-01 03:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "22285d36f29a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# § 3.2 — the canonical portfolio_type enum.
PORTFOLIO_CATEGORIES = [
    ("Entity_D_Core", "Entity D — Core", "Core fund holdings managed under Entity D."),
    ("Entity_D_Non_Core", "Entity D — Non-Core", "Non-core fund holdings under Entity D."),
    ("Entity_D_LLC", "Entity D — LLC", "LLC-structured holdings under Entity D."),
    ("Entity_E", "Entity E", "Holdings managed under Entity E."),
    ("Entity_A", "Entity A", "Holdings managed under Entity A."),
    ("Strategic_Equity", "Strategic Equity", "Strategic equity positions outside the main fund vehicles."),
    ("Entity_C", "Entity C", "Holdings managed under Entity C."),
    ("Real_Estate_Debt", "Real Estate Debt", "Debt instruments backed by real-estate collateral."),
]


def upgrade() -> None:
    portfolio_categories = op.create_table(
        "portfolio_categories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_portfolio_categories_code"),
    )

    op.bulk_insert(
        portfolio_categories,
        [
            {"code": code, "display_name": display_name, "description": description}
            for code, display_name, description in PORTFOLIO_CATEGORIES
        ],
    )

    op.create_table(
        "valuations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("valuation_date", sa.Date(), nullable=False),
        sa.Column("post_money_valuation_cr", sa.Numeric(precision=20, scale=4), nullable=False),
        sa.Column("pre_money_valuation_cr", sa.Numeric(precision=20, scale=4), nullable=True),
        sa.Column("currency", sa.String(length=10), server_default="INR", nullable=False),
        sa.Column("source", sa.String(length=64), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["company_id"], ["portfolio_companies.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_valuations_company_date",
        "valuations",
        ["company_id", "valuation_date"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_valuations_company_date", table_name="valuations")
    op.drop_table("valuations")
    op.drop_table("portfolio_categories")
