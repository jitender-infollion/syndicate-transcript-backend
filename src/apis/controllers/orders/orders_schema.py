from datetime import datetime
from typing import Literal

from pydantic import BaseModel

OrderStatusLiteral = Literal["created", "paid", "failed"]


class CreateOrderRequest(BaseModel):
    # amount/currency are unused - the server recomputes the real total.
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


class FreeOrderResponse(BaseModel):
    # Zero-amount order (or an existing order that's already paid) - nothing
    # to check out with Razorpay, so there's no razorpayOrderId/keyId to give
    # the frontend. Status will always be "paid" here.
    orderId: str
    status: OrderStatusLiteral
    transcriptIds: list[int]
    amount: int


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
