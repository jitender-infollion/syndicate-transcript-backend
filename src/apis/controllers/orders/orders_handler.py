import logging
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from apis.controllers.transcripts.transcripts_helper import has_transcript_access
from apis.models.order import Order, OrderItem, OrderStatus
from apis.models.payment import Payment, PaymentStatus
from apis.models.receipt import Receipt
from apis.models.transcript import Transcript
from apis.models.user import User
from services.database.postgres.connection import get_session
from services.email.email_service import send_invoice_email
from services.payment import RazorpayService
from services.receipt import generate_receipt_pdf

from .orders_helper import clear_purchased_cart_items, create_receipt, transition_to_failed, transition_to_paid
from .orders_schema import CreateOrderResponse, FreeOrderResponse, OrderSummary, VerifyPaymentResponse

logger = logging.getLogger(__name__)


class OrdersHandler:
    def __init__(self, payment_service: RazorpayService):
        self.payment_service = payment_service

    def _existing_order_response(self, session, order: Order) -> CreateOrderResponse | FreeOrderResponse:
        transcript_ids = [
            row[0] for row in session.query(OrderItem.transcript_id).filter(OrderItem.order_id == order.id).all()
        ]
        # Already paid (free order, or a real payment completed since this was
        # last checked) - nothing to resume with Razorpay.
        if order.status == OrderStatus.PAID.value:
            return FreeOrderResponse(
                orderId=str(order.id), status=order.status, transcriptIds=transcript_ids, amount=order.amount
            )
        payment = session.query(Payment).filter(Payment.order_id == order.id).first()
        return CreateOrderResponse(
            orderId=str(order.id),
            razorpayOrderId=payment.provider_order_id,
            transcriptIds=transcript_ids,
            amount=order.amount,
            currency=order.currency,
            keyId=self.payment_service.settings.payment.razorpay_key_id,
        )

    def create_order(
        self, user_id: int, transcript_ids: list[int], idempotency_key: str
    ) -> CreateOrderResponse | FreeOrderResponse:
        # Rate limiting (RateLimits.orders.CREATE_ORDER) happens in
        # rate_limit_create_order, wired onto this route as a dependency.
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
                if has_transcript_access(session, user_id, transcript_id):
                    raise HTTPException(status_code=400, detail="You already own one or more of these items.")

            # Reuse an already-open order for the same items - guards against
            # duplicate checkouts even with a different idempotency key (e.g. refresh).
            target_id_set = set(unique_ids)
            open_orders = (
                session.query(Order)
                .filter(Order.user_id == user_id, Order.status == OrderStatus.CREATED.value)
                .order_by(Order.created_at.desc())
                .all()
            )
            for candidate in open_orders:
                candidate_id_set = {
                    row[0]
                    for row in session.query(OrderItem.transcript_id).filter(OrderItem.order_id == candidate.id).all()
                }
                if candidate_id_set == target_id_set:
                    return self._existing_order_response(session, candidate)

            amount = sum(t.price for t in transcripts)
            currency = self.payment_service.currency

            # Zero-amount order (e.g. a free/promo transcript) - Razorpay
            # rejects zero-amount orders outright, and there's nothing to
            # actually pay for, so skip the gateway entirely and mark it paid
            # immediately, same end-state transition_to_paid would produce.
            if amount == 0:
                paid_at = datetime.utcnow()
                order = Order(
                    user_id=user_id,
                    status=OrderStatus.PAID.value,
                    amount=0,
                    currency=currency,
                    idempotency_key=idempotency_key,
                    paid_at=paid_at,
                )
                session.add(order)
                session.flush()

                session.add(
                    Payment(
                        order_id=order.id,
                        provider="free",
                        provider_order_id=f"free-order-{order.id}",
                        amount=0,
                        status=PaymentStatus.PAID.value,
                        paid_at=paid_at,
                    )
                )
                for transcript in transcripts:
                    session.add(
                        OrderItem(
                            order_id=order.id,
                            user_id=user_id,
                            transcript_id=transcript.id,
                            price=transcript.price,
                            currency=currency,
                        )
                    )
                session.flush()

                create_receipt(session, order, paid_at)
                clear_purchased_cart_items(session, order)

                try:
                    session.commit()
                except IntegrityError:
                    # Concurrent request won the idempotency-key race - return that order.
                    session.rollback()
                    existing = (
                        session.query(Order)
                        .filter(Order.user_id == user_id, Order.idempotency_key == idempotency_key)
                        .first()
                    )
                    return self._existing_order_response(session, existing)

                self._email_invoice_best_effort(session, order)
                return FreeOrderResponse(
                    orderId=str(order.id), status=order.status, transcriptIds=unique_ids, amount=0
                )

            receipt = f"order-{user_id}-{int(datetime.utcnow().timestamp())}"

            gateway_order = self.payment_service.create_order(amount, currency, receipt)
            if gateway_order is None:
                raise HTTPException(status_code=502, detail="Could not start payment. Please try again.")

            order = Order(
                user_id=user_id,
                status=OrderStatus.CREATED.value,
                amount=amount,
                currency=currency,
                idempotency_key=idempotency_key,
            )
            session.add(order)
            session.flush()

            session.add(
                Payment(
                    order_id=order.id,
                    provider="razorpay",
                    provider_order_id=gateway_order["id"],
                    amount=amount,
                    status=PaymentStatus.PENDING.value,
                )
            )

            for transcript in transcripts:
                session.add(
                    OrderItem(
                        order_id=order.id,
                        user_id=user_id,
                        transcript_id=transcript.id,
                        price=transcript.price,
                        currency=currency,
                    )
                )

            try:
                session.commit()
            except IntegrityError:
                # Concurrent request won the idempotency-key race - return that order.
                session.rollback()
                existing = (
                    session.query(Order)
                    .filter(Order.user_id == user_id, Order.idempotency_key == idempotency_key)
                    .first()
                )
                return self._existing_order_response(session, existing)

            return CreateOrderResponse(
                orderId=str(order.id),
                razorpayOrderId=gateway_order["id"],
                transcriptIds=unique_ids,
                amount=amount,
                currency=currency,
                keyId=self.payment_service.settings.payment.razorpay_key_id,
            )
        except HTTPException:
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
        # Runs after the paid-transition is committed - email failure can't affect it.
        try:
            receipt = session.query(Receipt).filter(Receipt.order_id == order.id).first()
            if receipt is None:
                return
            rows, user = self._load_receipt_data(session, order)
            pdf_bytes = generate_receipt_pdf(order, rows, user, receipt.invoice_number)
            send_invoice_email(user.email, user.name, receipt.invoice_number, pdf_bytes)
        except Exception:
            logger.exception("Failed to email invoice for order %s", order.id)

    def verify_payment(
        self, user_id: int, razorpay_order_id: str, razorpay_payment_id: str, razorpay_signature: str
    ) -> VerifyPaymentResponse:
        session = get_session()
        try:
            result = (
                session.query(Order, Payment)
                .join(Payment, Payment.order_id == Order.id)
                .filter(Payment.provider_order_id == razorpay_order_id, Order.user_id == user_id)
                .first()
            )
            if result is None:
                raise HTTPException(status_code=404, detail="Order not found")
            order, payment = result

            just_paid = False
            if order.status == OrderStatus.CREATED.value:
                if self.payment_service.verify_payment_signature(
                    razorpay_order_id, razorpay_payment_id, razorpay_signature
                ):
                    just_paid = transition_to_paid(
                        session, order, payment, razorpay_payment_id, provider_signature=razorpay_signature
                    )
                else:
                    transition_to_failed(session, order, payment)
                session.commit()

            session.refresh(order)
            if just_paid:
                self._email_invoice_best_effort(session, order)
            return VerifyPaymentResponse(orderId=str(order.id), status=order.status)
        except HTTPException:
            raise
        except Exception:
            session.rollback()
            logger.exception("Failed to verify payment")
            raise HTTPException(status_code=500, detail="Internal error") from None
        finally:
            session.close()

    def handle_webhook(self, gateway: str, raw_body: bytes, signature: str, event_id: str) -> None:
        if gateway != "razorpay":
            raise HTTPException(status_code=404, detail="Unknown payment gateway")

        # An unset webhook secret makes signature checks trivially forgeable.
        if not self.payment_service.settings.payment.is_configured:
            raise HTTPException(status_code=503, detail="Payments are not configured yet.")
        if not self.payment_service.verify_webhook_signature(raw_body, signature):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

        event = self.payment_service.parse_webhook_event(raw_body)
        if event is None or event.get("event_type") not in ("payment.captured", "payment.failed"):
            return

        session = get_session()
        try:
            result = (
                session.query(Order, Payment)
                .join(Payment, Payment.order_id == Order.id)
                .filter(Payment.provider_order_id == event["gateway_order_id"])
                .first()
            )
            if result is None:
                logger.warning("Webhook received for unknown gateway order %s", event["gateway_order_id"])
                return
            order, payment = result

            # Redelivered event id is a no-op, checked before the status guard below.
            if event_id and payment.webhook_event_id == event_id:
                return

            just_paid = False
            if order.status == OrderStatus.CREATED.value:
                if event["event_type"] == "payment.captured":
                    just_paid = transition_to_paid(
                        session,
                        order,
                        payment,
                        event["gateway_payment_id"],
                    )
                else:
                    transition_to_failed(session, order, payment)

            if event_id:
                session.query(Payment).filter(Payment.id == payment.id).update({"webhook_event_id": event_id})
            session.commit()

            if just_paid:
                self._email_invoice_best_effort(session, order)
        except HTTPException:
            raise
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
        except HTTPException:
            raise
        except Exception:
            session.rollback()
            logger.exception("Failed to list orders")
            raise HTTPException(status_code=500, detail="Internal error") from None
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
        except Exception:
            session.rollback()
            logger.exception("Failed to get order")
            raise HTTPException(status_code=500, detail="Internal error") from None
        finally:
            session.close()

    def get_receipt_pdf(self, user_id: int, order_id: int) -> bytes:
        session = get_session()
        try:
            order = session.query(Order).filter(Order.id == order_id, Order.user_id == user_id).first()
            if order is None or order.status != OrderStatus.PAID.value:
                raise HTTPException(status_code=404, detail="Receipt not available for this order")

            receipt = session.query(Receipt).filter(Receipt.order_id == order.id).first()
            if receipt is not None:
                invoice_number = receipt.invoice_number
            else:
                # Paid before the receipts table existed - compute without persisting.
                paid_at = order.paid_at or order.created_at
                invoice_number = f"INV-{paid_at:%Y%m%d}-{order.id:05d}"

            rows, user = self._load_receipt_data(session, order)
            return generate_receipt_pdf(order, rows, user, invoice_number)
        except HTTPException:
            raise
        except Exception:
            session.rollback()
            logger.exception("Failed to generate receipt")
            raise HTTPException(status_code=500, detail="Internal error") from None
        finally:
            session.close()
