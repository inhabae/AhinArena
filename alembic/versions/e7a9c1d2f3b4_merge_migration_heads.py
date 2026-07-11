"""merge migration heads

Revision ID: e7a9c1d2f3b4
Revises: 1d19a3c4e5f6, d6f4c8a1b2e3
Create Date: 2026-07-11 00:00:00.000000

"""
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "e7a9c1d2f3b4"
down_revision: Union[str, Sequence[str], None] = (
    "1d19a3c4e5f6",
    "d6f4c8a1b2e3",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
