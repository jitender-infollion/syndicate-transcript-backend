from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Index, Integer, String, Text, text
from sqlalchemy.orm import relationship

from services.database.postgres.connection import Base

from .schema import UserRole


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_anonymized_at_null", "anonymized_at", postgresql_where=text("anonymized_at IS NULL")),
    )

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=True)
    email = Column(String, unique=True, nullable=False, index=True)
    role = Column(String, nullable=False, default=UserRole.CUSTOMER.value, server_default=UserRole.CUSTOMER.value)
    email_verified = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    password = Column(Text, nullable=True)
    company_name = Column(String, nullable=True)
    active = Column(Boolean, nullable=False, default=True, server_default=text("true"))
    anonymized_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)

    otps = relationship("Otp", back_populates="user", cascade="all, delete-orphan")
