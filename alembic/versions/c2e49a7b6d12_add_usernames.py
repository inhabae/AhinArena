"""add usernames

Revision ID: c2e49a7b6d12
Revises: 8a4f1f3d7b20
Create Date: 2026-07-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c2e49a7b6d12"
down_revision: Union[str, Sequence[str], None] = "8a4f1f3d7b20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("username", sa.String(length=80), nullable=True))

    op.execute("UPDATE users SET username = email WHERE username IS NULL")

    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("username", nullable=False)
        batch_op.create_unique_constraint("uq_users_username", ["username"])
        batch_op.create_check_constraint(
            "ck_users_username_min_length",
            "length(username) >= 1",
        )
        batch_op.create_check_constraint(
            "ck_users_username_max_length",
            "length(username) <= 80",
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("ck_users_username_max_length", type_="check")
        batch_op.drop_constraint("ck_users_username_min_length", type_="check")
        batch_op.drop_constraint("uq_users_username", type_="unique")
        batch_op.drop_column("username")
