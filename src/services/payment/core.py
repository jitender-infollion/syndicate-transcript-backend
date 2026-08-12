import json
import logging

import razorpay
from razorpay.errors import SignatureVerificationError

logger = logging.getLogger(__name__)


class RazorpayService:
    def __init__(self, settings):
        self.settings = settings
        payment = settings.payment
        self.currency = payment.currency
        self.client = razorpay.Client(auth=(payment.razorpay_key_id, payment.razorpay_key_secret))
        self._webhook_secret = payment.razorpay_webhook_secret

    def create_order(self, amount: int, currency: str, receipt: str) -> dict | None:
        try:
            # Razorpay always expects amount in the currency's smallest unit
            # (e.g. cents for USD, paise for INR) - amount here is whole units,
            # matching transcripts.price and Order.amount.
            return self.client.order.create(
                {"amount": amount * 100, "currency": currency, "receipt": receipt, "payment_capture": 1}
            )
        except Exception:
            logger.exception("Razorpay order creation failed")
            return None

    def verify_payment_signature(self, order_id: str, payment_id: str, signature: str) -> bool:
        try:
            self.client.utility.verify_payment_signature(
                {
                    "razorpay_order_id": order_id,
                    "razorpay_payment_id": payment_id,
                    "razorpay_signature": signature,
                }
            )
            return True
        except SignatureVerificationError:
            return False
        except Exception:
            logger.exception("Razorpay payment signature verification errored")
            return False

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        try:
            self.client.utility.verify_webhook_signature(payload.decode("utf-8"), signature, self._webhook_secret)
            return True
        except SignatureVerificationError:
            return False
        except Exception:
            logger.exception("Razorpay webhook signature verification errored")
            return False

    def parse_webhook_event(self, payload: bytes) -> dict | None:
        try:
            data = json.loads(payload)
        except Exception:
            logger.exception("Failed to parse Razorpay webhook payload")
            return None

        entity = data.get("payload", {}).get("payment", {}).get("entity", {})
        return {
            "event_type": data.get("event"),
            "gateway_order_id": entity.get("order_id"),
            "gateway_payment_id": entity.get("id"),
        }
