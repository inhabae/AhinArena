"""rename move player to bot_id

Revision ID: 5d41a81f3c2b
Revises: f4a8b6c2d9e1
Create Date: 2026-07-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5d41a81f3c2b'
down_revision: Union[str, Sequence[str], None] = 'f4a8b6c2d9e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('moves', sa.Column('bot_id', sa.Integer(), nullable=True))
    op.execute(
        sa.text(
            """
            UPDATE moves
            SET bot_id = CASE player
                WHEN 'X' THEN (
                    SELECT bot_one_id FROM matches WHERE matches.id = moves.match_id
                )
                WHEN 'O' THEN (
                    SELECT bot_two_id FROM matches WHERE matches.id = moves.match_id
                )
            END
            """
        )
    )
    with op.batch_alter_table('moves') as batch_op:
        batch_op.alter_column('bot_id', existing_type=sa.Integer(), nullable=False)
        batch_op.create_foreign_key(
            'fk_moves_bot_id_bots',
            'bots',
            ['bot_id'],
            ['id'],
        )
        batch_op.drop_column('player')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('moves', sa.Column('player', sa.String(), nullable=True))
    op.execute(
        sa.text(
            """
            UPDATE moves
            SET player = CASE bot_id
                WHEN (
                    SELECT bot_one_id FROM matches WHERE matches.id = moves.match_id
                ) THEN 'X'
                WHEN (
                    SELECT bot_two_id FROM matches WHERE matches.id = moves.match_id
                ) THEN 'O'
            END
            """
        )
    )
    with op.batch_alter_table('moves') as batch_op:
        batch_op.alter_column('player', existing_type=sa.String(), nullable=False)
        batch_op.drop_constraint('fk_moves_bot_id_bots', type_='foreignkey')
        batch_op.drop_column('bot_id')
