from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)

from api.database import Base


class Bot(Base):
    __tablename__ = "bots"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String, nullable=False)

    game_id = Column(String, nullable=False)

    created_by = Column(String, nullable=False)

    rating = Column(Integer, nullable=False, default=1200, server_default="1200")
    games_played = Column(Integer, nullable=False, default=0, server_default="0")
    wins = Column(Integer, nullable=False, default=0, server_default="0")
    losses = Column(Integer, nullable=False, default=0, server_default="0")
    draws = Column(Integer, nullable=False, default=0, server_default="0")

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("game_id", "name", name="uq_bots_game_id_name"),
        CheckConstraint("rating >= 0", name="ck_bots_rating_non_negative"),
        CheckConstraint("games_played >= 0", name="ck_bots_games_played_non_negative"),
        CheckConstraint("wins >= 0", name="ck_bots_wins_non_negative"),
        CheckConstraint("losses >= 0", name="ck_bots_losses_non_negative"),
        CheckConstraint("draws >= 0", name="ck_bots_draws_non_negative"),
        CheckConstraint(
            "wins + losses + draws = games_played",
            name="ck_bots_record_matches_games_played",
        ),
        Index("ix_bots_game_id_rating", "game_id", "rating"),
    )
