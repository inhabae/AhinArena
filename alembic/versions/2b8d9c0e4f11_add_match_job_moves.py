"""add match job moves

Revision ID: 2b8d9c0e4f11
Revises: 7a6b5c4d3e2f
Create Date: 2026-07-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "2b8d9c0e4f11"
down_revision: Union[str, Sequence[str], None] = "7a6b5c4d3e2f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "match_job_moves",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("move_number", sa.Integer(), nullable=False),
        sa.Column("bot_id", sa.Integer(), nullable=False),
        sa.Column("move", sa.JSON(), nullable=False),
        sa.Column("board_state", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["bot_id"],
            ["bots.id"],
            name="fk_match_job_moves_bot_id_bots",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["match_jobs.id"],
            name="fk_match_job_moves_job_id_match_jobs",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "job_id",
            "move_number",
            name="uq_match_job_moves_job_id_move_number",
        ),
    )
    op.create_index(
        op.f("ix_match_job_moves_job_id"),
        "match_job_moves",
        ["job_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_match_job_moves_job_id"), table_name="match_job_moves")
    op.drop_table("match_job_moves")
