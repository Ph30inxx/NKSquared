"""dashboard_jobs table for AI PDF dashboard generator

Revision ID: i9d0e1f2g3h4
Revises: h8c9d0e1f2g3
Create Date: 2026-05-08

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "i9d0e1f2g3h4"
down_revision = "h8c9d0e1f2g3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE dashboard_jobs (
            id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            query        TEXT NOT NULL,
            title        TEXT,
            status       TEXT NOT NULL DEFAULT 'pending'
                             CHECK (status IN ('pending', 'generating', 'ready', 'failed')),
            pdf_path     TEXT,
            page_count   INTEGER,
            error_msg    TEXT,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            completed_at TIMESTAMPTZ
        )
    """)
    op.execute("CREATE INDEX idx_dashboard_jobs_user_id    ON dashboard_jobs(user_id)")
    op.execute("CREATE INDEX idx_dashboard_jobs_created_at ON dashboard_jobs(created_at DESC)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_dashboard_jobs_created_at")
    op.execute("DROP INDEX IF EXISTS idx_dashboard_jobs_user_id")
    op.execute("DROP TABLE IF EXISTS dashboard_jobs")
