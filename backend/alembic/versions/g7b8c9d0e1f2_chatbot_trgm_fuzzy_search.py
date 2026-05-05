"""chatbot: switch nk_validated_queries to trigram fuzzy search

Replaces the tsvector GIN index with a pg_trgm trigram GIN index.
This enables similarity() queries for fuzzy dedup and fuzzy search
instead of exact full-text token matching.

Revision ID: g7b8c9d0e1f2
Revises: d4e5f6a7b8c9
Create Date: 2026-05-05
"""
from typing import Sequence, Union
from alembic import op

revision: str = "g7b8c9d0e1f2"
down_revision: Union[str, None] = "f9b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("DROP INDEX IF EXISTS idx_nk_vq_question")
    op.execute(
        "CREATE INDEX idx_nk_vq_question_trgm "
        "ON nk_validated_queries USING gin(question gin_trgm_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_nk_vq_question_trgm")
    op.execute(
        "CREATE INDEX idx_nk_vq_question "
        "ON nk_validated_queries USING gin(to_tsvector('english', question))"
    )
