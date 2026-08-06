from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, text

from services.database.postgres.connection import Base


class SupportMessage(Base):
    __tablename__ = "support_messages"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    # Set only if the submitter happened to be logged in - this endpoint is
    # public, so it's never required.
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    # Kept for abuse investigation, alongside the IP rate limit on this route.
    ip_address = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=text("now()"), nullable=True)
