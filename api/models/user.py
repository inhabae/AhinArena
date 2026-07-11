from sqlalchemy import CheckConstraint, Column, DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import relationship

from api.database import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        CheckConstraint("length(email) <= 320", name="ck_users_email_max_length"),
        CheckConstraint("email LIKE '%_@_%._%'", name="ck_users_email_format"),
    )

    id = Column(Integer, primary_key=True, index=True)

    email = Column(String(320), nullable=False)
    password_hash = Column(String(255), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    sessions = relationship(
        "Session",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
