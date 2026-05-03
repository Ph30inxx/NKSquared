"""chatbot: add nk_validated_queries table for self-learning query store

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-05-03 12:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "nk_validated_queries",
        sa.Column("id",           sa.Integer(),                  primary_key=True),
        sa.Column("question",     sa.Text(),                     nullable=False),
        sa.Column("sql_query",    sa.Text(),                     nullable=False),
        sa.Column("explanation",  sa.Text(),                     nullable=False),
        sa.Column("tables_used",  sa.Text(),                     nullable=True),
        sa.Column("used_count",   sa.Integer(),                  nullable=False, server_default="0"),
        sa.Column("created_at",   sa.DateTime(timezone=True),    nullable=False, server_default=sa.func.now()),
        sa.Column("last_used_at", sa.DateTime(timezone=True),    nullable=True),
    )
    # GIN index for full-text search on the question column
    op.execute(
        "CREATE INDEX idx_nk_vq_question ON nk_validated_queries "
        "USING gin(to_tsvector('english', question))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_nk_vq_question")
    op.drop_table("nk_validated_queries")
