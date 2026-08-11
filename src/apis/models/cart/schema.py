from enum import Enum


class CartStatus(str, Enum):
    ACTIVE = "active"
    CONVERTED = "converted"
