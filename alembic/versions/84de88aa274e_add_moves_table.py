"""add moves table

Revision ID: 84de88aa274e
Revises: 0002_create_matches_table
Create Date: 2026-07-08 13:05:58.393055

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '84de88aa274e'
down_revision: Union[str, Sequence[str], None] = '0002_create_matches_table'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('moves',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('match_id', sa.Integer(), nullable=False),
    sa.Column('move_number', sa.Integer(), nullable=False),
    sa.Column('player', sa.String(), nullable=False),
    sa.Column('move', sa.JSON(), nullable=False),
    sa.ForeignKeyConstraint(['match_id'], ['matches.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('match_id', 'move_number', name='uq_moves_match_id_move_number')
    )
    op.create_index(op.f('ix_moves_id'), 'moves', ['id'], unique=False)
    op.create_index(op.f('ix_moves_match_id'), 'moves', ['match_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_moves_match_id'), table_name='moves')
    op.drop_index(op.f('ix_moves_id'), table_name='moves')
    op.drop_table('moves')
