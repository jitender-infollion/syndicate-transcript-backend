from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import relationship

from services.database.postgres.connection import Base


class Otp(Base):
    __tablename__ = "otp"
    __table_args__ = (Index("ix_otp_user_id_expire_time", "user_id", "expire_time"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    otp = Column(String, nullable=False)
    expire_time = Column(DateTime, nullable=False)
    retry_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="otps")
