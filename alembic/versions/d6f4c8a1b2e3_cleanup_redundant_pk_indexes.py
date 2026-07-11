"""cleanup redundant pk indexes

Revision ID: d6f4c8a1b2e3
Revises: c2e49a7b6d12
Create Date: 2026-07-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "d6f4c8a1b2e3"
down_revision: Union[str, Sequence[str], None] = "c2e49a7b6d12"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_index(op.f("ix_bots_id"), table_name="bots")
    op.drop_index(op.f("ix_matches_id"), table_name="matches")
    op.drop_index(op.f("ix_moves_id"), table_name="moves")
    op.drop_index(op.f("ix_users_id"), table_name="users")
    op.create_index("ix_matches_game_id", "matches", ["game_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_matches_game_id", table_name="matches")
    op.create_index(op.f("ix_users_id"), "users", ["id"], unique=False)
    op.create_index(op.f("ix_moves_id"), "moves", ["id"], unique=False)
    op.create_index(op.f("ix_matches_id"), "matches", ["id"], unique=False)
    op.create_index(op.f("ix_bots_id"), "bots", ["id"], unique=False)
