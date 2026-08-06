import logging
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from apis.controllers.transcripts.transcripts_handler import _has_active_entitlement
from apis.models.invoice import Invoice
from apis.models.order import Order, OrderItem, OrderStatus
from apis.models.transcript import Transcript
from apis.models.user import User
from services.database.postgres.connection import get_session
from services.email.email_service import send_invoice_email
from services.payment import RazorpayService
from services.receipt import generate_receipt_pdf

from .helpers import transition_to_failed, transition_to_paid
from .orders_schema import CreateOrderResponse, OrderSummary, VerifyPaymentResponse

logger = logging.getLogger(__name__)


class OrdersHandler:
    def __init__(self, payment_service: RazorpayService):
        self.payment_service = payment_service

    def _existing_order_response(self, session, order: Order) -> CreateOrderResponse:
        transcript_ids = [
            row[0] for row in session.query(OrderItem.transcript_id).filter(OrderItem.order_id == order.id).all()
        ]
        return CreateOrderResponse(
            orderId=str(order.id),
            razorpayOrderId=order.gateway_order_id,
            transcriptIds=transcript_ids,
            amount=order.amount,
            currency=order.currency,
            keyId=self.payment_service.settings.payment.razorpay_key_id,
        )

    def create_order(self, user_id: int, transcript_ids: list[int], idempotency_key: str) -> CreateOrderResponse:
        if not self.payment_service.settings.payment.is_configured:
            raise HTTPException(status_code=503, detail="Payments are not configured yet.")
        if not transcript_ids:
            raise HTTPException(status_code=400, detail="No items to check out.")

        session = get_session()
        try:
            existing = (
                session.query(Order)
                .filter(Order.user_id == user_id, Order.idempotency_key == idempotency_key)
                .first()
            )
            if existing is not None:
                return self._existing_order_response(session, existing)

            unique_ids = list(dict.fromkeys(transcript_ids))
            transcripts = (
                session.query(Transcript).filter(Transcript.id.in_(unique_ids), Transcript.is_active.is_(True)).all()
            )
            if len(transcripts) != len(unique_ids):
                raise HTTPException(status_code=400, detail="One or more items are no longer available.")

            for transcript_id in unique_ids:
                if _has_active_entitlement(session, user_id, transcript_id):
                    raise HTTPException(status_code=400, detail="You already own one or more of these items.")

            amount = sum(t.price for t in transcripts)
            currency = self.payment_service.currency
            receipt = f"order-{user_id}-{int(datetime.utcnow().timestamp())}"

            # Razorpay wants the smallest currency unit (cents/paise) - amount
            # here is whole units, same convention as transcripts.price.
            gateway_order = self.payment_service.create_order(amount * 100, currency, receipt)
            if gateway_order is None:
                raise HTTPException(status_code=502, detail="Could not start payment. Please try again.")

            order = Order(
                user_id=user_id,
                status=OrderStatus.CREATED.value,
                amount=amount,
                currency=currency,
                gateway="razorpay",
                gateway_order_id=gateway_order["id"],
                idempotency_key=idempotency_key,
            )
            session.add(order)
            session.flush()

            for transcript in transcripts:
                session.add(OrderItem(order_id=order.id, transcript_id=transcript.id, price=transcript.price))

            try:
                session.commit()
            except IntegrityError:
                # Concurrent request with the same idempotency key won the race -
                # not an error, return that order instead of creating a duplicate.
                session.rollback()
                existing = (
                    session.query(Order)
                    .filter(Order.user_id == user_id, Order.idempotency_key == idempotency_key)
                    .first()
                )
                return self._existing_order_response(session, existing)

            return CreateOrderResponse(
                orderId=str(order.id),
                razorpayOrderId=order.gateway_order_id,
                transcriptIds=unique_ids,
                amount=amount,
                currency=currency,
                keyId=self.payment_service.settings.payment.razorpay_key_id,
            )
        except HTTPException:
            session.rollback()
            raise
        except Exception:
            session.rollback()
            logger.exception("Failed to create order")
            raise HTTPException(status_code=500, detail="Internal error") from None
        finally:
            session.close()

    def _load_receipt_data(self, session, order: Order):
        rows = (
            session.query(OrderItem.price, Transcript.topic)
            .join(Transcript, Transcript.id == OrderItem.transcript_id)
            .filter(OrderItem.order_id == order.id)
            .all()
        )
        user = session.query(User).filter(User.id == order.user_id).first()
        return rows, user

    def _email_invoice_best_effort(self, session, order: Order) -> None:
        # Runs only after the paid-transition is already committed - a slow or
        # failing email must never affect payment/entitlement correctness.
        try:
            invoice = session.query(Invoice).filter(Invoice.order_id == order.id).first()
            if invoice is None:
                return
            rows, user = self._load_receipt_data(session, order)
            pdf_bytes = generate_receipt_pdf(order, rows, user, invoice.invoice_number)
            send_invoice_email(user.email, user.name, invoice.invoice_number, pdf_bytes)
        except Exception:
            logger.exception("Failed to email invoice for order %s", order.id)

    def verify_payment(
        self, user_id: int, razorpay_order_id: str, razorpay_payment_id: str, razorpay_signature: str
    ) -> VerifyPaymentResponse:
        session = get_session()
        try:
            order = (
                session.query(Order)
                .filter(Order.gateway_order_id == razorpay_order_id, Order.user_id == user_id)
                .first()
            )
            if order is None:
                raise HTTPException(status_code=404, detail="Order not found")

            just_paid = False
            if order.status == OrderStatus.CREATED.value:
                if self.payment_service.verify_payment_signature(
                    razorpay_order_id, razorpay_payment_id, razorpay_signature
                ):
                    just_paid = transition_to_paid(session, order, razorpay_payment_id)
                else:
                    transition_to_failed(session, order)
                session.commit()

            session.refresh(order)
            if just_paid:
                self._email_invoice_best_effort(session, order)
            return VerifyPaymentResponse(orderId=str(order.id), status=order.status)
        except HTTPException:
            session.rollback()
            raise
        except Exception:
            session.rollback()
            logger.exception("Failed to verify payment")
            raise HTTPException(status_code=500, detail="Internal error") from None
        finally:
            session.close()

    def handle_webhook(self, raw_body: bytes, signature: str, event_id: str) -> None:
        if not self.payment_service.verify_webhook_signature(raw_body, signature):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

        event = self.payment_service.parse_webhook_event(raw_body)
        if event is None or event.get("event_type") not in ("payment.captured", "payment.failed"):
            return

        session = get_session()
        try:
            order = session.query(Order).filter(Order.gateway_order_id == event["gateway_order_id"]).first()
            if order is None:
                logger.warning("Webhook received for unknown gateway order %s", event["gateway_order_id"])
                return

            # Razorpay's documented idempotency check: a redelivered event id is
            # a no-op before any status check even runs, not just relying on the
            # 'created' state guard below.
            if event_id and order.last_webhook_event_id == event_id:
                return

            just_paid = False
            if order.status == OrderStatus.CREATED.value:
                if event["event_type"] == "payment.captured":
                    just_paid = transition_to_paid(session, order, event["gateway_payment_id"])
                else:
                    transition_to_failed(session, order)

            if event_id:
                order.last_webhook_event_id = event_id
            session.commit()

            if just_paid:
                self._email_invoice_best_effort(session, order)
        except Exception:
            session.rollback()
            logger.exception("Failed to process payment webhook")
            raise HTTPException(status_code=500, detail="Internal error") from None
        finally:
            session.close()

    def list_orders(self, user_id: int) -> list[OrderSummary]:
        session = get_session()
        try:
            orders = session.query(Order).filter(Order.user_id == user_id).order_by(Order.created_at.desc()).all()
            order_ids = [o.id for o in orders]
            items_by_order: dict[int, list[int]] = {}
            if order_ids:
                rows = (
                    session.query(OrderItem.order_id, OrderItem.transcript_id)
                    .filter(OrderItem.order_id.in_(order_ids))
                    .all()
                )
                for order_id, transcript_id in rows:
                    items_by_order.setdefault(order_id, []).append(transcript_id)

            return [
                OrderSummary(
                    id=str(o.id),
                    transcripts=items_by_order.get(o.id, []),
                    amount=o.amount,
                    status=o.status,
                    createdAt=o.created_at,
                )
                for o in orders
            ]
        finally:
            session.close()

    def get_order(self, user_id: int, order_id: int) -> OrderSummary:
        session = get_session()
        try:
            order = session.query(Order).filter(Order.id == order_id, Order.user_id == user_id).first()
            if order is None:
                raise HTTPException(status_code=404, detail="Order not found")
            transcript_ids = [
                row[0] for row in session.query(OrderItem.transcript_id).filter(OrderItem.order_id == order.id).all()
            ]
            return OrderSummary(
                id=str(order.id),
                transcripts=transcript_ids,
                amount=order.amount,
                status=order.status,
                createdAt=order.created_at,
            )
        except HTTPException:
            raise
        finally:
            session.close()

    def get_receipt_pdf(self, user_id: int, order_id: int) -> bytes:
        session = get_session()
        try:
            order = session.query(Order).filter(Order.id == order_id, Order.user_id == user_id).first()
            if order is None or order.status != OrderStatus.PAID.value:
                raise HTTPException(status_code=404, detail="Receipt not available for this order")

            invoice = session.query(Invoice).filter(Invoice.order_id == order.id).first()
            if invoice is not None:
                invoice_number = invoice.invoice_number
            else:
                # Paid before the invoices table existed - compute the same way,
                # without persisting (this is a read path).
                paid_at = order.paid_at or order.created_at
                invoice_number = f"INV-{paid_at:%Y%m%d}-{order.id:05d}"

            rows, user = self._load_receipt_data(session, order)
            return generate_receipt_pdf(order, rows, user, invoice_number)
        except HTTPException:
            raise
        finally:
            session.close()
