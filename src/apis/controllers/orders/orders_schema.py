from datetime import datetime
from typing import Literal

from pydantic import BaseModel

OrderStatusLiteral = Literal["created", "paid", "failed"]


class CreateOrderRequest(BaseModel):
    # amount/currency are accepted for schema validation only - the server
    # always recomputes the real total from Transcript.price and ignores these.
    amount: int
    currency: str
    transcriptIds: list[int]


class CreateOrderResponse(BaseModel):
    orderId: str
    razorpayOrderId: str
    transcriptIds: list[int]
    amount: int
    currency: str
    keyId: str


class VerifyPaymentRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class VerifyPaymentResponse(BaseModel):
    orderId: str
    status: OrderStatusLiteral


class OrderSummary(BaseModel):
    id: str
    transcripts: list[int]
    amount: int
    status: OrderStatusLiteral
    createdAt: datetime | None
