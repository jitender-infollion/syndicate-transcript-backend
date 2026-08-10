from datetime import datetime

from apis.models.entitlement import Entitlement, EntitlementSource, EntitlementStatus
from apis.models.invoice import Invoice
from apis.models.order import Order, OrderItem, OrderStatus
from apis.models.payment import Payment, PaymentStatus


def grant_entitlements(session, order: Order) -> None:
    items = session.query(OrderItem).filter(OrderItem.order_id == order.id).all()
    for item in items:
        existing = (
            session.query(Entitlement)
            .filter(Entitlement.user_id == order.user_id, Entitlement.transcript_id == item.transcript_id)
            .first()
        )
        if existing:
            existing.status = EntitlementStatus.ACTIVE.value
            existing.revoked_at = None
            existing.order_item_id = item.id
        else:
            session.add(
                Entitlement(
                    user_id=order.user_id,
                    transcript_id=item.transcript_id,
                    order_item_id=item.id,
                    status=EntitlementStatus.ACTIVE.value,
                    source=EntitlementSource.PURCHASE.value,
                )
            )


def create_invoice(session, order: Order, paid_at: datetime) -> Invoice:
    invoice = Invoice(
        order_id=order.id,
        user_id=order.user_id,
        invoice_number=f"INV-{paid_at:%Y%m%d}-{order.id:05d}",
        amount=order.amount,
        currency=order.currency,
    )
    session.add(invoice)
    session.flush()
    return invoice


def transition_to_paid(
    session,
    order: Order,
    payment: Payment,
    gateway_payment_id: str,
    provider_signature: str | None = None,
) -> bool:
    # Guarded UPDATE, only if still 'created' - lets verify and the webhook race safely.
    paid_at = datetime.utcnow()
    rowcount = (
        session.query(Order)
        .filter(Order.id == order.id, Order.status == OrderStatus.CREATED.value)
        .update({"status": OrderStatus.PAID.value, "paid_at": paid_at})
    )
    if rowcount:
        session.query(Payment).filter(Payment.id == payment.id).update(
            {
                "status": PaymentStatus.PAID.value,
                "provider_payment_id": gateway_payment_id,
                "provider_signature": provider_signature,
                "paid_at": paid_at,
            }
        )
        grant_entitlements(session, order)
        create_invoice(session, order, paid_at)
    return bool(rowcount)


def transition_to_failed(session, order: Order, payment: Payment) -> None:
    rowcount = session.query(Order).filter(Order.id == order.id, Order.status == OrderStatus.CREATED.value).update(
        {"status": OrderStatus.FAILED.value}
    )
    if rowcount:
        session.query(Payment).filter(Payment.id == payment.id).update({"status": PaymentStatus.FAILED.value})
