from datetime import datetime

from apis.models.order import Order, OrderStatus
from apis.models.payment import Payment, PaymentStatus
from apis.models.receipt import Receipt


def create_receipt(session, order: Order, paid_at: datetime) -> Receipt:
    receipt = Receipt(
        order_id=order.id,
        invoice_number=f"INV-{paid_at:%Y%m%d}-{order.id:05d}",
        amount=order.amount,
        currency=order.currency,
    )
    session.add(receipt)
    session.flush()
    return receipt


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
        create_receipt(session, order, paid_at)
    return bool(rowcount)


def transition_to_failed(session, order: Order, payment: Payment) -> None:
    rowcount = session.query(Order).filter(Order.id == order.id, Order.status == OrderStatus.CREATED.value).update(
        {"status": OrderStatus.FAILED.value}
    )
    if rowcount:
        session.query(Payment).filter(Payment.id == payment.id).update({"status": PaymentStatus.FAILED.value})
