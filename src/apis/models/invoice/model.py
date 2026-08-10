from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, text

from services.database.postgres.connection import Base


# amount/currency are a snapshot of what was charged, independent of later order changes.
class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, unique=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    invoice_number = Column(String, nullable=False, unique=True, index=True)

    amount = Column(Integer, nullable=False)
    currency = Column(String, nullable=False)

    issued_at = Column(DateTime, server_default=text("now()"), nullable=True)

    pdf_storage_key = Column(String, nullable=True)
