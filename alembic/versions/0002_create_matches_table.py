"""Create matches table.

Revision ID: 0002_create_matches_table
Revises: 0001_initial_database_baseline
Create Date: 2026-07-08 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0002_create_matches_table"
down_revision: str | None = "0001_initial_database_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "matches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("game_id", sa.String(), nullable=False),
        sa.Column("bot_one_id", sa.String(), nullable=False),
        sa.Column("bot_two_id", sa.String(), nullable=False),
        sa.Column("winner", sa.String(), nullable=True),
        sa.Column("result_reason", sa.String(), nullable=False),
        sa.Column("move_history", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_matches_id"), "matches", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_matches_id"), table_name="matches")
    op.drop_table("matches")
