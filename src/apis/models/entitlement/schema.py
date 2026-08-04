from enum import Enum


class EntitlementStatus(str, Enum):
    ACTIVE = "active"
    REVOKED = "revoked"


class EntitlementSource(str, Enum):
    PURCHASE = "purchase"
    ADMIN_GRANT = "admin_grant"
