from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Index, String

from services.database.postgres.connection import Base


class Session(Base):
    __tablename__ = "sessions"
    __table_args__ = (Index("ix_sessions_user_id_revoked_at", "user_id", "revoked_at"),)

    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    refresh_token_hash = Column(String, unique=True, nullable=False, index=True)
    device_info = Column(String, nullable=True)
    ip_address = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
