from sqlalchemy import CheckConstraint, Column, DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import relationship

from api.database import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        UniqueConstraint("username", name="uq_users_username"),
        CheckConstraint("length(email) <= 320", name="ck_users_email_max_length"),
        CheckConstraint("length(username) >= 1", name="ck_users_username_min_length"),
        CheckConstraint("length(username) <= 80", name="ck_users_username_max_length"),
        CheckConstraint("length(description) <= 280", name="ck_users_description_max_length"),
        CheckConstraint("email LIKE '%_@_%._%'", name="ck_users_email_format"),
    )

    id = Column(Integer, primary_key=True)

    email = Column(String(320), nullable=False)
    username = Column(String(80), nullable=False)
    description = Column(Text, nullable=False, default="", server_default="")
    password_hash = Column(String(255), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    sessions = relationship(
        "Session",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
