from sqlalchemy import Column, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import relationship

from api.database import Base


class Move(Base):
    __tablename__ = "moves"
    __table_args__ = (
        UniqueConstraint("match_id", "move_number", name="uq_moves_match_id_move_number"),
    )

    id = Column(Integer, primary_key=True, index=True)

    match_id = Column(Integer, ForeignKey("matches.id"), nullable=False, index=True)

    move_number = Column(Integer, nullable=False)

    player = Column(String, nullable=False)

    move = Column(JSON, nullable=False)

    match = relationship("Match", back_populates="moves")
