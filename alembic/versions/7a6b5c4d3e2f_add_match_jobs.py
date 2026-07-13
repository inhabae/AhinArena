"""add match jobs

Revision ID: 7a6b5c4d3e2f
Revises: 3f2a1b0c9d8e
Create Date: 2026-07-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7a6b5c4d3e2f"
down_revision: Union[str, Sequence[str], None] = "3f2a1b0c9d8e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "match_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("game_id", sa.String(), nullable=False),
        sa.Column("bot_one_id", sa.Integer(), nullable=False),
        sa.Column("bot_two_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), server_default="queued", nullable=False),
        sa.Column("match_id", sa.Integer(), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status in ('queued', 'running', 'completed', 'failed')",
            name="ck_match_jobs_status",
        ),
        sa.ForeignKeyConstraint(
            ["bot_one_id"],
            ["bots.id"],
            name="fk_match_jobs_bot_one_id_bots",
        ),
        sa.ForeignKeyConstraint(
            ["bot_two_id"],
            ["bots.id"],
            name="fk_match_jobs_bot_two_id_bots",
        ),
        sa.ForeignKeyConstraint(
            ["match_id"],
            ["matches.id"],
            name="fk_match_jobs_match_id_matches",
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("match_jobs")
