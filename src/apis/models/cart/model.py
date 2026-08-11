from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Index, String, UniqueConstraint, text

from services.database.postgres.connection import Base

from .schema import CartStatus


# guest_id is a backend-issued cookie value for unauthenticated carts.
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

    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    guest_id = Column(String, nullable=True, index=True)
    status = Column(String, nullable=False, default=CartStatus.ACTIVE.value, server_default=CartStatus.ACTIVE.value)
    created_at = Column(DateTime, server_default=text("now()"), nullable=True)
    expires_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=True)


class CartItem(Base):
    __tablename__ = "cart_items"
    __table_args__ = (UniqueConstraint("cart_id", "transcript_id", name="uq_cart_items_cart_transcript"),)

    id = Column(BigInteger, primary_key=True, index=True)
    cart_id = Column(BigInteger, ForeignKey("carts.id", ondelete="CASCADE"), nullable=False)
    transcript_id = Column(BigInteger, ForeignKey("transcripts.id"), nullable=False)
    created_at = Column(DateTime, server_default=text("now()"), nullable=True)
