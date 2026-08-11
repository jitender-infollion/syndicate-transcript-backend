from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, String, text

from services.database.postgres.connection import Base


# amount/currency are a snapshot of what was charged, independent of later order changes.
class Receipt(Base):
    __tablename__ = "receipts"

    id = Column(BigInteger, primary_key=True, index=True)
    order_id = Column(BigInteger, ForeignKey("orders.id"), nullable=False, unique=True, index=True)

    invoice_number = Column(String, nullable=False, unique=True, index=True)

    amount = Column(Integer, nullable=False)
    currency = Column(String, nullable=False)

    issued_at = Column(DateTime, server_default=text("now()"), nullable=True)

    pdf_url = Column(String, nullable=True)
