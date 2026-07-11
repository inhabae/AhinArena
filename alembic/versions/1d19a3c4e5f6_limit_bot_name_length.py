"""limit bot name length

Revision ID: 1d19a3c4e5f6
Revises: c2e49a7b6d12
Create Date: 2026-07-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "1d19a3c4e5f6"
down_revision: Union[str, Sequence[str], None] = "c2e49a7b6d12"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("bots") as batch_op:
        batch_op.alter_column(
            "name",
            existing_type=sa.String(),
            type_=sa.String(length=64),
            existing_nullable=False,
        )
        batch_op.create_check_constraint(
            "ck_bots_name_max_length",
            "length(name) <= 64",
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("bots") as batch_op:
        batch_op.drop_constraint("ck_bots_name_max_length", type_="check")
        batch_op.alter_column(
            "name",
            existing_type=sa.String(length=64),
            type_=sa.String(),
            existing_nullable=False,
        )
