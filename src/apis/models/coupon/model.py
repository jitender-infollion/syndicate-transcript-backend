import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID

from services.database.postgres.connection import Base


class Coupon(Base):
    __tablename__ = "coupons"
    __table_args__ = (
        Index("ix_coupons_is_active_valid_from_valid_until", "is_active", "valid_from", "valid_until"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    code = Column(String, nullable=False, unique=True, index=True)
    discount_type = Column(String, nullable=False)
    discount_value = Column(Integer, nullable=False)
    max_discount_amount = Column(Integer, nullable=True)
    min_order_amount = Column(Integer, nullable=True, default=0, server_default=text("0"))
    usage_limit = Column(Integer, nullable=True)
    usage_count = Column(Integer, nullable=False, default=0, server_default=text("0"))
    per_user_limit = Column(Integer, nullable=True, default=1, server_default=text("1"))
    is_stackable = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    valid_from = Column(DateTime, nullable=True)
    valid_until = Column(DateTime, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default=text("true"))
    created_at = Column(DateTime, server_default=text("now()"), nullable=True)


# discount_applied is a snapshot, kept even if the coupon is later edited.
class CouponRedemption(Base):
    __tablename__ = "coupon_redemptions"
    __table_args__ = (Index("ix_coupon_redemptions_coupon_id_user_id", "coupon_id", "user_id"),)

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    coupon_id = Column(UUID(as_uuid=True), ForeignKey("coupons.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False, unique=True, index=True)
    discount_applied = Column(Integer, nullable=False)
    redeemed_at = Column(DateTime, server_default=text("now()"), nullable=True)
