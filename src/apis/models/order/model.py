from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, text

from services.database.postgres.connection import Base

from .schema import OrderStatus


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (Index("ix_orders_user_id_status", "user_id", "status"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    status = Column(String, nullable=False, default=OrderStatus.CREATED.value, server_default=OrderStatus.CREATED.value)
    # Whole currency units, same convention as transcripts.price - server-computed
    # from Transcript.price at checkout time, never trusted from the client.
    amount = Column(Integer, nullable=False)
    currency = Column(String, nullable=False)
    # Which RazorpayService (or future gateway) handled this order.
    gateway = Column(String, nullable=False)
    gateway_order_id = Column(String, nullable=False, unique=True, index=True)
    gateway_payment_id = Column(String, nullable=True, unique=True, index=True)
    # Last Razorpay X-Razorpay-Event-Id successfully processed for this order -
    # a replayed webhook with the same event id is a no-op before any state
    # check even runs (Razorpay's documented idempotency recommendation).
    last_webhook_event_id = Column(String, nullable=True)
    # Client-generated key (one per checkout attempt) - required by the create
    # order endpoint, not enforced NOT NULL here so the column stays usable for
    # any future non-client-driven order creation path.
    idempotency_key = Column(String, nullable=True, unique=True, index=True)
    created_at = Column(DateTime, server_default=text("now()"), nullable=True)
    paid_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=True)


class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (UniqueConstraint("order_id", "transcript_id", name="uq_order_items_order_transcript"),)

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    transcript_id = Column(Integer, ForeignKey("transcripts.id"), nullable=False)
    # Snapshot of transcript.price at checkout time - a later price change
    # must never retroactively change what a past order actually charged.
    price = Column(Integer, nullable=False)
    created_at = Column(DateTime, server_default=text("now()"), nullable=True)
