from sqlalchemy import Column, DateTime, Index, Integer, String, func

from api.database import Base


class AuthRateLimitEvent(Base):
    __tablename__ = "auth_rate_limit_events"
    __table_args__ = (
        Index(
            "ix_auth_rate_limit_events_bucket_key_created_at",
            "bucket",
            "key",
            "created_at",
        ),
    )

    id = Column(Integer, primary_key=True)
    bucket = Column(String(64), nullable=False)
    key = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
