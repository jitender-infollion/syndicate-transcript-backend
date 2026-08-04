from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, text

from services.database.postgres.connection import Base

from .schema import CartStatus


class Cart(Base):
    __tablename__ = "carts"
    __table_args__ = (
        Index("ix_carts_user_id_status", "user_id", "status"),
        Index(
            "uq_carts_active_user",
            "user_id",
            unique=True,
            postgresql_where=text("status = 'active' AND user_id IS NOT NULL"),
        ),
        Index(
            "uq_carts_active_guest",
            "guest_id",
            unique=True,
            postgresql_where=text("status = 'active' AND guest_id IS NOT NULL"),
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    # Backend-issued cookie value for unauthenticated carts (see cart_handler / routes/cart.py).
    guest_id = Column(String, nullable=True, index=True)
    status = Column(String, nullable=False, default=CartStatus.ACTIVE.value, server_default=CartStatus.ACTIVE.value)
    created_at = Column(DateTime, server_default=text("now()"), nullable=True)
    # Only set for guest carts; drives a future abandoned-cart cleanup job, not built yet.
    expires_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=True)


class CartItem(Base):
    __tablename__ = "cart_items"
    __table_args__ = (UniqueConstraint("cart_id", "transcript_id", name="uq_cart_items_cart_transcript"),)

    id = Column(Integer, primary_key=True, index=True)
    cart_id = Column(Integer, ForeignKey("carts.id", ondelete="CASCADE"), nullable=False)
    transcript_id = Column(Integer, ForeignKey("transcripts.id"), nullable=False)
    created_at = Column(DateTime, server_default=text("now()"), nullable=True)
