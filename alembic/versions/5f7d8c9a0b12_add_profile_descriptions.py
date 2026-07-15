"""add profile descriptions

Revision ID: 5f7d8c9a0b12
Revises: 2b8d9c0e4f11
Create Date: 2026-07-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "5f7d8c9a0b12"
down_revision: Union[str, Sequence[str], None] = "2b8d9c0e4f11"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(
            sa.Column(
                "description",
                sa.Text(),
                server_default="",
                nullable=False,
            )
        )
        batch_op.create_check_constraint(
            "ck_users_description_max_length",
            "length(description) <= 280",
        )

    with op.batch_alter_table("bots") as batch_op:
        batch_op.add_column(
            sa.Column(
                "description",
                sa.Text(),
                server_default="",
                nullable=False,
            )
        )
        batch_op.create_check_constraint(
            "ck_bots_description_max_length",
            "length(description) <= 280",
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("bots") as batch_op:
        batch_op.drop_constraint("ck_bots_description_max_length", type_="check")
        batch_op.drop_column("description")

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("ck_users_description_max_length", type_="check")
        batch_op.drop_column("description")
