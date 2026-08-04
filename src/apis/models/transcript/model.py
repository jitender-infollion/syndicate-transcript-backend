from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, JSON, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import relationship

from services.database.postgres.connection import Base


class Transcript(Base):
    __tablename__ = "transcripts"
    __table_args__ = (
        Index("ix_transcripts_domain", "domain", postgresql_using="gin"),
        Index("ix_transcripts_geography", "geography", postgresql_using="gin"),
        Index("ix_transcripts_is_active_published_at", "is_active", "published_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    author_id = Column(Integer, ForeignKey("authors.id"), nullable=False, index=True)
    topic = Column(String, nullable=True)
    # A transcript can belong to multiple domains/geographies - matched via
    # array containment (e.g. domain @> ARRAY['Healthcare']), not equality.
    domain = Column(ARRAY(String), nullable=True)
    geography = Column(ARRAY(String), nullable=True)
    preview = Column(Text, nullable=True)
    # {"fileName": "<original file name>", "url": "<permanent S3 object url/key>"}.
    # Never served as-is - view/download endpoints mint a fresh signed URL from
    # this reference on every request, so the stored value itself is never
    # exposed to the client.
    final_transcript = Column(JSON, nullable=True)
    key_insight = Column(ARRAY(String), nullable=True)
    published_at = Column(DateTime, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    price = Column(Integer, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True, server_default=text("true"))
    created_at = Column(DateTime, server_default=text("now()"), nullable=True)

    author = relationship("Author")
