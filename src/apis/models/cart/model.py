from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String, UniqueConstraint, text

from services.database.postgres.connection import Base


# guest_id is a backend-issued cookie value for unauthenticated carts.
# One cart per user (or per guest), reused for the account's lifetime -
# never recreated, just emptied and refilled on the next add-to-cart.
class Cart(Base):
    __tablename__ = "carts"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_carts_user_id"),
        UniqueConstraint("guest_id", name="uq_carts_guest_id"),
    )

    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    guest_id = Column(String, nullable=True, index=True)
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
