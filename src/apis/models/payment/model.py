from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, text

from services.database.postgres.connection import Base

from .schema import PaymentStatus


# provider_order_id is the lookup key for both the verify callback and the webhook.
class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        UniqueConstraint("provider", "provider_order_id", name="uq_payments_provider_order_id"),
        UniqueConstraint("provider", "provider_payment_id", name="uq_payments_provider_payment_id"),
        Index("ix_payments_order_id", "order_id"),
    )

    id = Column(BigInteger, primary_key=True, index=True)
    order_id = Column(BigInteger, ForeignKey("orders.id"), nullable=False)
    provider = Column(String, nullable=False)
    provider_order_id = Column(String, nullable=False)
    provider_payment_id = Column(String, nullable=True)
    provider_signature = Column(String, nullable=True)
    amount = Column(Integer, nullable=False)
    status = Column(
        String, nullable=False, default=PaymentStatus.PENDING.value, server_default=PaymentStatus.PENDING.value
    )
    webhook_event_id = Column(String, nullable=True, unique=True)
    paid_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=text("now()"), nullable=True)
