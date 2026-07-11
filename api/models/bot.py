from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from api.database import Base
from api.ratings import DEFAULT_ELO_RATING


class Bot(Base):
    __tablename__ = "bots"

    id = Column(Integer, primary_key=True)

    name = Column(String(64), nullable=False)

    game_id = Column(String, nullable=False)

    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    owner = relationship("User")

    rating = Column(
        Integer,
        nullable=False,
        default=DEFAULT_ELO_RATING,
        server_default=str(DEFAULT_ELO_RATING),
    )
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
        CheckConstraint("length(name) <= 64", name="ck_bots_name_max_length"),
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
