"""sprint 8: mis_templates table, submission template_id + parse cache, audit/MIS indexes

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-05-05 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mis_templates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.String(length=20), nullable=True),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("sheet_name_pattern", sa.String(length=120), nullable=True),
        sa.Column("header_row", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "period_orientation",
            sa.String(length=10),
            nullable=False,
            server_default="columns",
        ),
        sa.Column(
            "row_mappings",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_mis_template_company", "mis_templates", ["company_id"], unique=False)
    # One default template per company (allowing multiple NULL company_id globals).
    op.execute(
        "CREATE UNIQUE INDEX uq_mis_template_default "
        "ON mis_templates(company_id) WHERE is_default;"
    )

    # Link MIS submissions back to the template that produced them.
    op.add_column(
        "mis_submissions",
        sa.Column("template_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_mis_submissions_template",
        "mis_submissions",
        "mis_templates",
        ["template_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "mis_submissions",
        sa.Column("last_parse_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "mis_submissions",
        sa.Column(
            "last_parse_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.create_index(
        "idx_mis_submissions_status_period",
        "mis_submissions",
        ["status", "period_year", "period_month"],
        unique=False,
    )

    # Sprint 8 perf pass: faster recent-first audit queries.
    op.create_index(
        "idx_audit_log_occurred_at",
        "audit_log",
        [sa.text("occurred_at DESC")],
        unique=False,
    )

    # Seed the two legacy hardcoded templates so they appear in the builder UI
    # and existing submissions can be tied back to them. They stay company-agnostic
    # (company_id NULL) and are not marked default — the parser falls back to
    # sheet-name detection when no DB template applies, which still picks them up.
    op.execute(
        """
        INSERT INTO mis_templates
            (company_id, name, version, is_default, sheet_name_pattern,
             header_row, period_orientation, row_mappings,
             created_at, updated_at)
        VALUES
            (NULL, 'Legacy v1 — Consolidated MIS FY 2026', 1, false,
             '^Consolidated MIS FY 2026$', 1, 'columns',
             '[{"_legacy": "v1"}]'::jsonb, NOW(), NOW()),
            (NULL, 'Legacy v2 — MIS Report FY25-26', 1, false,
             '^MIS Report FY25-26$', 1, 'columns',
             '[{"_legacy": "v2"}]'::jsonb, NOW(), NOW());
        """
    )


def downgrade() -> None:
    op.drop_index("idx_audit_log_occurred_at", table_name="audit_log")
    op.drop_index("idx_mis_submissions_status_period", table_name="mis_submissions")
    op.drop_column("mis_submissions", "last_parse_payload")
    op.drop_column("mis_submissions", "last_parse_at")
    op.drop_constraint("fk_mis_submissions_template", "mis_submissions", type_="foreignkey")
    op.drop_column("mis_submissions", "template_id")

    op.execute("DROP INDEX IF EXISTS uq_mis_template_default;")
    op.drop_index("idx_mis_template_company", table_name="mis_templates")
    op.drop_table("mis_templates")
