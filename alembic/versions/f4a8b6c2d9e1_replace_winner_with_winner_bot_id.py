"""replace winner marker with winner bot id

Revision ID: f4a8b6c2d9e1
Revises: c9a16f2d8b4e
Create Date: 2026-07-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f4a8b6c2d9e1"
down_revision: Union[str, Sequence[str], None] = "c9a16f2d8b4e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("matches") as batch_op:
        batch_op.add_column(sa.Column("winner_bot_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_matches_winner_bot_id_bots",
            "bots",
            ["winner_bot_id"],
            ["id"],
        )
    op.execute(
        sa.text(
            """
            UPDATE matches
            SET winner_bot_id = CASE
                WHEN winner = 'X' THEN bot_one_id
                WHEN winner = 'O' THEN bot_two_id
                ELSE NULL
            END
            """
        )
    )
    with op.batch_alter_table("matches") as batch_op:
        batch_op.drop_column("winner")


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("matches") as batch_op:
        batch_op.add_column(sa.Column("winner", sa.String(), nullable=True))
    op.execute(
        sa.text(
            """
            UPDATE matches
            SET winner = CASE
                WHEN winner_bot_id = bot_one_id THEN 'X'
                WHEN winner_bot_id = bot_two_id THEN 'O'
                ELSE NULL
            END
            """
        )
    )
    with op.batch_alter_table("matches") as batch_op:
        batch_op.drop_constraint(
            "fk_matches_winner_bot_id_bots",
            type_="foreignkey",
        )
        batch_op.drop_column("winner_bot_id")
