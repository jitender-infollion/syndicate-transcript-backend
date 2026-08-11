from enum import Enum


class DiscountType(str, Enum):
    PERCENTAGE = "percentage"
    FLAT = "flat"
