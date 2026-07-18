"""replace source submissions with executable artifacts

Revision ID: 6c1a7e9d2b40
Revises: f1b2c3d4e5a6
Create Date: 2026-07-18 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "6c1a7e9d2b40"
down_revision: Union[str, Sequence[str], None] = "f1b2c3d4e5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("bots") as batch_op:
        batch_op.add_column(
            sa.Column("latest_submission_version", sa.Integer(), server_default="0", nullable=False)
        )

    op.execute(
        "UPDATE bots SET latest_submission_version = COALESCE("
        "(SELECT MAX(version) FROM bot_submissions WHERE bot_submissions.bot_id = bots.id), 0)"
    )
    op.execute("UPDATE bots SET active_submission_id = NULL")
    op.execute("DELETE FROM bot_submissions")

    with op.batch_alter_table("bot_submissions") as batch_op:
        batch_op.drop_column("source_code")
        batch_op.drop_column("language")
        batch_op.add_column(sa.Column("executable", sa.LargeBinary(), nullable=False))
        batch_op.add_column(sa.Column("executable_size", sa.Integer(), nullable=False))
        batch_op.add_column(sa.Column("executable_digest", sa.String(length=64), nullable=False))
        batch_op.add_column(sa.Column("original_filename", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.execute("UPDATE bots SET active_submission_id = NULL")
    op.execute("DELETE FROM bot_submissions")
    with op.batch_alter_table("bot_submissions") as batch_op:
        batch_op.drop_column("original_filename")
        batch_op.drop_column("executable_digest")
        batch_op.drop_column("executable_size")
        batch_op.drop_column("executable")
        batch_op.add_column(sa.Column("language", sa.String(), nullable=False, server_default="python"))
        batch_op.add_column(sa.Column("source_code", sa.Text(), nullable=False, server_default=""))
    with op.batch_alter_table("bots") as batch_op:
        batch_op.drop_column("latest_submission_version")
