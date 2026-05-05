"""add chat_conversations table

Revision ID: f9b2c3d4e5f6
Revises: f6a7b8c9d0e1
Create Date: 2026-05-04
"""
from alembic import op
import sqlalchemy as sa

revision = "f9b2c3d4e5f6"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chat_conversations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False, server_default="New Conversation"),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("session_id", name="uq_chat_conv_session_id"),
    )
    op.create_index("idx_chat_conv_user_id", "chat_conversations", ["user_id"])
    op.create_index("idx_chat_conv_updated_at", "chat_conversations", ["updated_at"])


def downgrade() -> None:
    op.drop_index("idx_chat_conv_updated_at", "chat_conversations")
    op.drop_index("idx_chat_conv_user_id", "chat_conversations")
    op.drop_table("chat_conversations")
