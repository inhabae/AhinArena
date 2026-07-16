"""add auth rate limit events

Revision ID: a8c3d2e1f4b5
Revises: 9b7d6a5c4e31
Create Date: 2026-07-16 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a8c3d2e1f4b5"
down_revision: Union[str, Sequence[str], None] = "9b7d6a5c4e31"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "auth_rate_limit_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bucket", sa.String(length=64), nullable=False),
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_auth_rate_limit_events_bucket_key_created_at",
        "auth_rate_limit_events",
        ["bucket", "key", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_auth_rate_limit_events_bucket_key_created_at",
        table_name="auth_rate_limit_events",
    )
    op.drop_table("auth_rate_limit_events")
