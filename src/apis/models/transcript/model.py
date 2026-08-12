from sqlalchemy import BigInteger, Boolean, Column, DateTime, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

from services.database.postgres.connection import Base


# final_transcript is never served as-is - a fresh signed URL is minted per request.
class Transcript(Base):
    __tablename__ = "transcripts"
    __table_args__ = (
        Index("ix_transcripts_domain", "domain", postgresql_using="gin"),
        Index("ix_transcripts_geography", "geography", postgresql_using="gin"),
        Index("ix_transcripts_is_active_published_at", "is_active", "published_at"),
    )

    id = Column(BigInteger, primary_key=True, index=True)
    fk_expert = Column(BigInteger, nullable=False, index=True)  # external id from the expert-management backend, no local FK
    expert_name = Column(String, nullable=True)  # snapshot of expert name at time of publishing
    designation = Column(String, nullable=True)  # snapshot of expert designation at time of publishing
    years_of_experience = Column(Integer, nullable=True)
    topic = Column(String, nullable=True)
    domain = Column(ARRAY(String), nullable=True)
    geography = Column(ARRAY(String), nullable=True)
    preview = Column(Text, nullable=True)
    final_transcript = Column(JSONB, nullable=True)
    key_insight = Column(ARRAY(String), nullable=True)
    published_at = Column(DateTime, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    price = Column(Integer, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True, server_default=text("true"))
    created_at = Column(DateTime, server_default=text("now()"), nullable=True)
