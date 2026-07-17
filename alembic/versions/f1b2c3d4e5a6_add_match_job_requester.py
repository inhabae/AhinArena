"""add match job requester

Revision ID: f1b2c3d4e5a6
Revises: a8c3d2e1f4b5
Create Date: 2026-07-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f1b2c3d4e5a6"
down_revision: Union[str, Sequence[str], None] = "a8c3d2e1f4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("match_jobs") as batch_op:
        batch_op.add_column(sa.Column("requester_user_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_match_jobs_requester_user_id_users",
            "users",
            ["requester_user_id"],
            ["id"],
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("match_jobs") as batch_op:
        batch_op.drop_constraint("fk_match_jobs_requester_user_id_users", type_="foreignkey")
        batch_op.drop_column("requester_user_id")
