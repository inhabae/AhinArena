"""add bot version ratings

Revision ID: 4e8f3a2b1c90
Revises: d9e0f1a2b3c4
Create Date: 2026-07-20 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "4e8f3a2b1c90"
down_revision: Union[str, None] = "d9e0f1a2b3c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("bot_submissions", sa.Column("rating", sa.Float(), server_default="1200", nullable=False))
    op.add_column("bot_submissions", sa.Column("games_played", sa.Integer(), server_default="0", nullable=False))
    op.add_column("bot_submissions", sa.Column("wins", sa.Integer(), server_default="0", nullable=False))
    op.add_column("bot_submissions", sa.Column("losses", sa.Integer(), server_default="0", nullable=False))
    op.add_column("bot_submissions", sa.Column("draws", sa.Integer(), server_default="0", nullable=False))
    op.add_column("matches", sa.Column("bot_one_submission_id", sa.Integer(), nullable=True))
    op.add_column("matches", sa.Column("bot_two_submission_id", sa.Integer(), nullable=True))

    op.create_foreign_key(
        "fk_matches_bot_one_submission_id_bot_submissions",
        "matches",
        "bot_submissions",
        ["bot_one_submission_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_matches_bot_two_submission_id_bot_submissions",
        "matches",
        "bot_submissions",
        ["bot_two_submission_id"],
        ["id"],
    )
    op.create_check_constraint(
        "ck_bot_submissions_rating_non_negative",
        "bot_submissions",
        "rating >= 0",
    )
    op.create_check_constraint(
        "ck_bot_submissions_games_played_non_negative",
        "bot_submissions",
        "games_played >= 0",
    )
    op.create_check_constraint(
        "ck_bot_submissions_wins_non_negative",
        "bot_submissions",
        "wins >= 0",
    )
    op.create_check_constraint(
        "ck_bot_submissions_losses_non_negative",
        "bot_submissions",
        "losses >= 0",
    )
    op.create_check_constraint(
        "ck_bot_submissions_draws_non_negative",
        "bot_submissions",
        "draws >= 0",
    )
    op.create_check_constraint(
        "ck_bot_submissions_record_matches_games_played",
        "bot_submissions",
        "wins + losses + draws = games_played",
    )


def downgrade() -> None:
    op.drop_constraint("ck_bot_submissions_record_matches_games_played", "bot_submissions", type_="check")
    op.drop_constraint("ck_bot_submissions_draws_non_negative", "bot_submissions", type_="check")
    op.drop_constraint("ck_bot_submissions_losses_non_negative", "bot_submissions", type_="check")
    op.drop_constraint("ck_bot_submissions_wins_non_negative", "bot_submissions", type_="check")
    op.drop_constraint("ck_bot_submissions_games_played_non_negative", "bot_submissions", type_="check")
    op.drop_constraint("ck_bot_submissions_rating_non_negative", "bot_submissions", type_="check")
    op.drop_constraint("fk_matches_bot_two_submission_id_bot_submissions", "matches", type_="foreignkey")
    op.drop_constraint("fk_matches_bot_one_submission_id_bot_submissions", "matches", type_="foreignkey")
    op.drop_column("matches", "bot_two_submission_id")
    op.drop_column("matches", "bot_one_submission_id")
    op.drop_column("bot_submissions", "draws")
    op.drop_column("bot_submissions", "losses")
    op.drop_column("bot_submissions", "wins")
    op.drop_column("bot_submissions", "games_played")
    op.drop_column("bot_submissions", "rating")
