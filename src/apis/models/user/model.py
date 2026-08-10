from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Index, Integer, String, Text, text
from sqlalchemy.ext.hybrid import hybrid_property

from services.crypto.email_crypto import decrypt_email, encrypt_email, hash_email
from services.database.postgres.connection import Base

from .schema import UserRole


# email is never stored in plaintext - use the `email` property, not email_encrypted directly.
class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_anonymized_at_null", "anonymized_at", postgresql_where=text("anonymized_at IS NULL")),
    )

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=True)
    email_encrypted = Column(Text, nullable=False)
    email_hash = Column(String, unique=True, nullable=False, index=True)
    role = Column(String, nullable=False, default=UserRole.CUSTOMER.value, server_default=UserRole.CUSTOMER.value)
    email_verified = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    password_hash = Column(Text, nullable=True)
    company_name = Column(String, nullable=True)
    active = Column(Boolean, nullable=False, default=True, server_default=text("true"))

    failed_login_attempts = Column(Integer, nullable=False, default=0, server_default=text("0"))
    locked_until = Column(DateTime, nullable=True)

    otp_hash = Column(String, nullable=True)
    otp_expire_time = Column(DateTime, nullable=True)
    otp_retry_count = Column(Integer, nullable=False, default=0, server_default=text("0"))

    reset_token_hash = Column(String, nullable=True)
    reset_token_expire_at = Column(DateTime, nullable=True)
    reset_requested_at = Column(DateTime, nullable=True)

    anonymized_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)

    @hybrid_property
    def email(self) -> str:
        return decrypt_email(self.email_encrypted)

    @email.setter
    def email(self, value: str) -> None:
        self.email_encrypted = encrypt_email(value)
        self.email_hash = hash_email(value)
