"""Add LLM settings table

Revision ID: 002
Revises: 001
Create Date: 2024-01-12 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ===========================================
    # LLM Settings Table
    # ===========================================
    op.create_table(
        "llm_settings",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("api_key", sa.Text(), nullable=True),
        sa.Column("model", sa.String(255), nullable=True),
        sa.Column("base_url", sa.String(500), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "user_id", name="uq_llm_settings_provider_user"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_llm_settings_user_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_llm_settings_provider", "llm_settings", ["provider"])
    op.create_index("ix_llm_settings_user_id", "llm_settings", ["user_id"])
    op.create_index("ix_llm_settings_is_default", "llm_settings", ["is_default"])


def downgrade() -> None:
    op.drop_index("ix_llm_settings_is_default", table_name="llm_settings")
    op.drop_index("ix_llm_settings_user_id", table_name="llm_settings")
    op.drop_index("ix_llm_settings_provider", table_name="llm_settings")
    op.drop_table("llm_settings")
