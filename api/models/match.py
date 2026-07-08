from sqlalchemy import Column, DateTime, Integer, JSON, String, func

from api.database import Base


class Match(Base):
    __tablename__ = "matches"

    id = Column(Integer, primary_key=True, index=True)

    game_id = Column(String, nullable=False)

    bot_one_id = Column(String, nullable=False)
    bot_two_id = Column(String, nullable=False)

    winner = Column(String, nullable=True)
    result_reason = Column(String, nullable=False)

    move_history = Column(JSON, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
