from enum import Enum


class OrderStatus(str, Enum):
    CREATED = "created"
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    CANCELLED = "cancelled"
