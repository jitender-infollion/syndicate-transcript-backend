from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, text

from services.database.postgres.connection import Base

from .schema import OrderStatus


# idempotency_key uniqueness is scoped to the user, not global - client-generated,
# so a global constraint would let one user's collision crash another's checkout.
class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        Index("ix_orders_user_id_status", "user_id", "status"),
        UniqueConstraint("user_id", "idempotency_key", name="uq_orders_user_idempotency_key"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    status = Column(String, nullable=False, default=OrderStatus.CREATED.value, server_default=OrderStatus.CREATED.value)
    amount = Column(Integer, nullable=False)
    currency = Column(String, nullable=False)
    idempotency_key = Column(String, nullable=True, index=True)
    created_at = Column(DateTime, server_default=text("now()"), nullable=True)
    paid_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=True)


# price is a snapshot at checkout time - later price changes don't affect it.
class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (UniqueConstraint("order_id", "transcript_id", name="uq_order_items_order_transcript"),)

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    transcript_id = Column(Integer, ForeignKey("transcripts.id"), nullable=False)
    price = Column(Integer, nullable=False)
    created_at = Column(DateTime, server_default=text("now()"), nullable=True)
