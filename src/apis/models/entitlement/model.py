from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint

from services.database.postgres.connection import Base

from .schema import EntitlementSource, EntitlementStatus


# order_item_id is nullable because admin_grant entitlements have no order item.
class Entitlement(Base):
    __tablename__ = "entitlements"
    __table_args__ = (
        UniqueConstraint("user_id", "transcript_id", name="uq_entitlements_user_transcript"),
        Index("ix_entitlements_user_id_status", "user_id", "status"),
        Index("ix_entitlements_order_item_id", "order_item_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    transcript_id = Column(Integer, ForeignKey("transcripts.id"), nullable=False)
    order_item_id = Column(Integer, ForeignKey("order_items.id"), nullable=True)
    status = Column(
        String, nullable=False, default=EntitlementStatus.ACTIVE.value, server_default=EntitlementStatus.ACTIVE.value
    )
    source = Column(
        String,
        nullable=False,
        default=EntitlementSource.PURCHASE.value,
        server_default=EntitlementSource.PURCHASE.value,
    )
    granted_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
