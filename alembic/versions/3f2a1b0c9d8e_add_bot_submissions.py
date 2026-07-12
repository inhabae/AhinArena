"""add bot submissions

Revision ID: 3f2a1b0c9d8e
Revises: e7a9c1d2f3b4
Create Date: 2026-07-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "3f2a1b0c9d8e"
down_revision: Union[str, Sequence[str], None] = "e7a9c1d2f3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "bot_submissions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bot_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("language", sa.String(), nullable=False),
        sa.Column("source_code", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["bot_id"],
            ["bots.id"],
            name="fk_bot_submissions_bot_id_bots",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "bot_id",
            "version",
            name="uq_bot_submissions_bot_id_version",
        ),
    )

    with op.batch_alter_table("bots") as batch_op:
        batch_op.add_column(sa.Column("active_submission_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_bots_active_submission_id_bot_submissions",
            "bot_submissions",
            ["active_submission_id"],
            ["id"],
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("bots") as batch_op:
        batch_op.drop_constraint(
            "fk_bots_active_submission_id_bot_submissions",
            type_="foreignkey",
        )
        batch_op.drop_column("active_submission_id")

    op.drop_table("bot_submissions")
