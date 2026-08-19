import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID

from services.database.postgres.connection import Base


# amount/currency are a snapshot of what was charged, independent of later order changes.
class Receipt(Base):
    __tablename__ = "receipts"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False, unique=True, index=True)

    invoice_number = Column(String, nullable=False, unique=True, index=True)

    amount = Column(Integer, nullable=False)
    currency = Column(String, nullable=False)

    issued_at = Column(DateTime, server_default=text("now()"), nullable=True)

    pdf_url = Column(String, nullable=True)
