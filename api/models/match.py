from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from api.database import Base


class Match(Base):
    __tablename__ = "matches"

    id = Column(Integer, primary_key=True, index=True)

    game_id = Column(String, nullable=False)

    bot_one_id = Column(Integer, ForeignKey("bots.id"), nullable=False)
    bot_two_id = Column(Integer, ForeignKey("bots.id"), nullable=False)

    winner = Column(String, nullable=True)
    result_reason = Column(String, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    bot_one = relationship("Bot", foreign_keys=[bot_one_id])
    bot_two = relationship("Bot", foreign_keys=[bot_two_id])

    moves = relationship(
        "Move",
        back_populates="match",
        cascade="all, delete-orphan",
        order_by="Move.move_number",
    )
