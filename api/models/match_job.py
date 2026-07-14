from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship

from api.database import Base


class MatchJob(Base):
    __tablename__ = "match_jobs"

    id = Column(Integer, primary_key=True)

    game_id = Column(String, nullable=False)
    bot_one_id = Column(Integer, ForeignKey("bots.id"), nullable=False)
    bot_two_id = Column(Integer, ForeignKey("bots.id"), nullable=False)
    status = Column(String, nullable=False, default="queued", server_default="queued")
    match_id = Column(Integer, ForeignKey("matches.id"), nullable=True)
    attempts = Column(Integer, nullable=False, default=0, server_default="0")
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    bot_one = relationship("Bot", foreign_keys=[bot_one_id])
    bot_two = relationship("Bot", foreign_keys=[bot_two_id])
    match = relationship("Match")
    moves = relationship(
        "MatchJobMove",
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="MatchJobMove.move_number",
    )

    __table_args__ = (
        CheckConstraint(
            "status in ('queued', 'running', 'completed', 'failed')",
            name="ck_match_jobs_status",
        ),
    )
