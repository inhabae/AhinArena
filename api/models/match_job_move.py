from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, UniqueConstraint, func
from sqlalchemy.orm import relationship

from api.database import Base


class MatchJobMove(Base):
    __tablename__ = "match_job_moves"
    __table_args__ = (
        UniqueConstraint("job_id", "move_number", name="uq_match_job_moves_job_id_move_number"),
    )

    id = Column(Integer, primary_key=True)

    job_id = Column(Integer, ForeignKey("match_jobs.id"), nullable=False, index=True)
    move_number = Column(Integer, nullable=False)
    bot_id = Column(Integer, ForeignKey("bots.id"), nullable=False)
    move = Column(JSON, nullable=False)
    board_state = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    job = relationship("MatchJob", back_populates="moves")
    bot = relationship("Bot")
