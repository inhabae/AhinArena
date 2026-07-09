"""add match rating snapshots

Revision ID: c9a16f2d8b4e
Revises: 8c7c4a566f78
Create Date: 2026-07-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c9a16f2d8b4e"
down_revision: Union[str, Sequence[str], None] = "8c7c4a566f78"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


RATING_COLUMNS = (
    "bot_one_rating_before",
    "bot_two_rating_before",
    "bot_one_rating_after",
    "bot_two_rating_after",
    "bot_one_rating_delta",
    "bot_two_rating_delta",
)


def upgrade() -> None:
    """Upgrade schema."""
    for column_name in RATING_COLUMNS:
        op.add_column(
            "matches",
            sa.Column(
                column_name,
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
        )

    with op.batch_alter_table("matches") as batch_op:
        for column_name in RATING_COLUMNS:
            batch_op.alter_column(column_name, server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    for column_name in reversed(RATING_COLUMNS):
        op.drop_column("matches", column_name)
