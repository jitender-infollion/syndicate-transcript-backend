from .orders_handler import OrdersHandler
from .orders_schema import (
    CreateOrderRequest,
    CreateOrderResponse,
    OrderSummary,
    VerifyPaymentRequest,
    VerifyPaymentResponse,
)


class OrdersController:
    def __init__(self, handler: OrdersHandler):
        self.handler = handler

    def create_order(self, user_id: int, body: CreateOrderRequest, idempotency_key: str) -> CreateOrderResponse:
        return self.handler.create_order(user_id, body.transcriptIds, idempotency_key)

    def verify_payment(self, user_id: int, body: VerifyPaymentRequest) -> VerifyPaymentResponse:
        return self.handler.verify_payment(
            user_id, body.razorpay_order_id, body.razorpay_payment_id, body.razorpay_signature
        )

    def list_orders(self, user_id: int) -> list[OrderSummary]:
        return self.handler.list_orders(user_id)

    def get_order(self, user_id: int, order_id: int) -> OrderSummary:
        return self.handler.get_order(user_id, order_id)

    def get_receipt_pdf(self, user_id: int, order_id: int) -> bytes:
        return self.handler.get_receipt_pdf(user_id, order_id)

    def handle_webhook(self, raw_body: bytes, signature: str, event_id: str) -> None:
        self.handler.handle_webhook(raw_body, signature, event_id)
