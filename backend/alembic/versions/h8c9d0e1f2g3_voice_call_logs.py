"""voice: add voice_call_logs table

Revision ID: h8c9d0e1f2g3
Revises: g7b8c9d0e1f2
Create Date: 2026-05-05
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "h8c9d0e1f2g3"
down_revision: Union[str, None] = "g7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "voice_call_logs",
        sa.Column("id",             sa.Integer(),                  primary_key=True),
        sa.Column("call_id",        sa.Text(),                     nullable=False),
        sa.Column("tool_name",      sa.Text(),                     nullable=False),
        sa.Column("user_query",     sa.Text(),                     nullable=False),
        sa.Column("result_preview", sa.Text(),                     nullable=True),
        sa.Column("latency_ms",     sa.Integer(),                  nullable=True),
        sa.Column("user_id",        sa.Integer(),                  nullable=True),
        sa.Column("created_at",     sa.DateTime(timezone=True),    server_default=sa.func.now()),
    )
    op.create_index("idx_vcl_call_id", "voice_call_logs", ["call_id"])
    op.create_index("idx_vcl_user_id", "voice_call_logs", ["user_id"])


def downgrade() -> None:
    op.drop_index("idx_vcl_user_id")
    op.drop_index("idx_vcl_call_id")
    op.drop_table("voice_call_logs")
