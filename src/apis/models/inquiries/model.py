from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, text

from services.database.postgres.connection import Base

from .schema import RequestStatus


# user_id is set only if the submitter was logged in - this endpoint is public.
class SupportMessage(Base):
    __tablename__ = "support_messages"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    status = Column(String, nullable=False, default=RequestStatus.OPEN.value, server_default=RequestStatus.OPEN.value)
    created_at = Column(DateTime, server_default=text("now()"), nullable=True)


class TopicRequest(Base):
    __tablename__ = "topic_requests"

    id = Column(Integer, primary_key=True, index=True)
    topic = Column(String, nullable=True)
    domain = Column(String, nullable=False)
    email = Column(String, nullable=False)
    remark = Column(Text, nullable=True)
    suggested_expert_name = Column(String, nullable=True)
    suggested_expert_linkedin = Column(String, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    status = Column(String, nullable=False, default=RequestStatus.OPEN.value, server_default=RequestStatus.OPEN.value)
    created_at = Column(DateTime, server_default=text("now()"), nullable=True)
