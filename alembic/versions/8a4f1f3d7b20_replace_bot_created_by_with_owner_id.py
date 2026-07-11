"""replace bot created_by with owner_id

Revision ID: 8a4f1f3d7b20
Revises: 49ec82f79706
Create Date: 2026-07-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8a4f1f3d7b20"
down_revision: Union[str, Sequence[str], None] = "49ec82f79706"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("bots") as batch_op:
        batch_op.add_column(sa.Column("owner_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_bots_owner_id_users",
            "users",
            ["owner_id"],
            ["id"],
        )
        batch_op.drop_column("created_by")


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("bots") as batch_op:
        batch_op.add_column(
            sa.Column("created_by", sa.String(), nullable=False, server_default="system")
        )
        batch_op.drop_constraint("fk_bots_owner_id_users", type_="foreignkey")
        batch_op.drop_column("owner_id")
        batch_op.alter_column("created_by", server_default=None)
