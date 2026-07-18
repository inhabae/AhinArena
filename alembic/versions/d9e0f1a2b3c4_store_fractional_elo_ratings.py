"""store fractional Elo ratings

Revision ID: d9e0f1a2b3c4
Revises: 6c1a7e9d2b40
Create Date: 2026-07-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d9e0f1a2b3c4"
down_revision: Union[str, Sequence[str], None] = "6c1a7e9d2b40"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Change Elo ratings and rating snapshots to floating point."""
    with op.batch_alter_table("bots") as batch_op:
        batch_op.alter_column(
            "rating",
            existing_type=sa.Integer(),
            type_=sa.Float(),
            existing_nullable=False,
            existing_server_default="1200",
        )

    with op.batch_alter_table("matches") as batch_op:
        for column in (
            "bot_one_rating_before",
            "bot_two_rating_before",
            "bot_one_rating_after",
            "bot_two_rating_after",
            "bot_one_rating_delta",
            "bot_two_rating_delta",
        ):
            batch_op.alter_column(
                column,
                existing_type=sa.Integer(),
                type_=sa.Float(),
                existing_nullable=False,
            )


def downgrade() -> None:
    """Round fractional ratings when restoring integer columns."""
    with op.batch_alter_table("matches") as batch_op:
        for column in (
            "bot_one_rating_before",
            "bot_two_rating_before",
            "bot_one_rating_after",
            "bot_two_rating_after",
            "bot_one_rating_delta",
            "bot_two_rating_delta",
        ):
            batch_op.alter_column(
                column,
                existing_type=sa.Float(),
                type_=sa.Integer(),
                existing_nullable=False,
            )

    with op.batch_alter_table("bots") as batch_op:
        batch_op.alter_column(
            "rating",
            existing_type=sa.Float(),
            type_=sa.Integer(),
            existing_nullable=False,
            existing_server_default="1200",
            server_default="1200",
        )
