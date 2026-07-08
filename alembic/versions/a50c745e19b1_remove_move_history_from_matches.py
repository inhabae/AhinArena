"""remove move_history from matches

Revision ID: a50c745e19b1
Revises: 84de88aa274e
Create Date: 2026-07-08 13:09:20.513417

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a50c745e19b1'
down_revision: Union[str, Sequence[str], None] = '84de88aa274e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_column('matches', 'move_history')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        'matches',
        sa.Column('move_history', sa.JSON(), nullable=False, server_default='[]'),
    )
    op.alter_column('matches', 'move_history', server_default=None)
