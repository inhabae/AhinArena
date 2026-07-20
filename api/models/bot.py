from sqlalchemy import (
    CheckConstraint,
    LargeBinary,
    Column,
    DateTime,
    ForeignKey,
    Float,
    Index,
    Integer,
    String,
    Text,
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
    description = Column(Text, nullable=False, default="", server_default="")

    game_id = Column(String, nullable=False)

    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    owner = relationship("User")

    active_submission_id = Column(
        Integer,
        ForeignKey("bot_submissions.id"),
        nullable=True,
    )
    active_submission = relationship(
        "BotSubmission",
        foreign_keys=[active_submission_id],
        post_update=True,
    )
    latest_submission_version = Column(Integer, nullable=False, default=0, server_default="0")
    submissions = relationship(
        "BotSubmission",
        back_populates="bot",
        cascade="all, delete-orphan",
        foreign_keys="BotSubmission.bot_id",
        order_by="BotSubmission.version",
    )

    rating = Column(
        Float,
        nullable=False,
        default=DEFAULT_ELO_RATING,
        server_default="1200",
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
        CheckConstraint("length(description) <= 280", name="ck_bots_description_max_length"),
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


class BotSubmission(Base):
    __tablename__ = "bot_submissions"

    id = Column(Integer, primary_key=True)

    bot_id = Column(Integer, ForeignKey("bots.id"), nullable=False)
    bot = relationship("Bot", back_populates="submissions", foreign_keys=[bot_id])

    version = Column(Integer, nullable=False)
    executable = Column(LargeBinary, nullable=False)
    executable_size = Column(Integer, nullable=False)
    executable_digest = Column(String(64), nullable=False)
    original_filename = Column(String(255), nullable=True)
    rating = Column(
        Float,
        nullable=False,
        default=DEFAULT_ELO_RATING,
        server_default="1200",
    )
    games_played = Column(Integer, nullable=False, default=0, server_default="0")
    wins = Column(Integer, nullable=False, default=0, server_default="0")
    losses = Column(Integer, nullable=False, default=0, server_default="0")
    draws = Column(Integer, nullable=False, default=0, server_default="0")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("bot_id", "version", name="uq_bot_submissions_bot_id_version"),
        CheckConstraint("rating >= 0", name="ck_bot_submissions_rating_non_negative"),
        CheckConstraint("games_played >= 0", name="ck_bot_submissions_games_played_non_negative"),
        CheckConstraint("wins >= 0", name="ck_bot_submissions_wins_non_negative"),
        CheckConstraint("losses >= 0", name="ck_bot_submissions_losses_non_negative"),
        CheckConstraint("draws >= 0", name="ck_bot_submissions_draws_non_negative"),
        CheckConstraint(
            "wins + losses + draws = games_played",
            name="ck_bot_submissions_record_matches_games_played",
        ),
    )
