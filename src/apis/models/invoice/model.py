from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, text

from services.database.postgres.connection import Base


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    # One invoice per paid order - unique enforces that relationship at the DB level.
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, unique=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Durable identifier, generated once at issue time and never recomputed.
    invoice_number = Column(String, nullable=False, unique=True, index=True)

    # Snapshot of what was actually charged - must never depend on the order
    # row still saying the same thing later (e.g. after a future refund).
    amount = Column(Integer, nullable=False)
    currency = Column(String, nullable=False)

    issued_at = Column(DateTime, server_default=text("now()"), nullable=True)

    # Key into the same object storage already used for transcript files
    # (see services/storage/signing_client) - unused for now, the PDF is only
    # ever generated on-demand/at send-time, never persisted.
    pdf_storage_key = Column(String, nullable=True)
