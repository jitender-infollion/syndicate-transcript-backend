import uuid

from fastapi import HTTPException, Request

from apis.controllers.orders.orders_controller import OrdersController
from apis.controllers.orders.orders_handler import OrdersHandler
from config import get_settings
from services.payment import RazorpayService


def get_current_user_id(request: Request) -> uuid.UUID:
    """User id attached by the JWT middleware. Use on every protected route."""
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="User identity missing from session.")
    return uuid.UUID(user_id)


def get_current_user_id_optional(request: Request) -> uuid.UUID | None:
    # Like get_current_user_id, but None instead of 401 - for soft-auth routes (e.g. cart).
    user_id = getattr(request.state, "user_id", None)
    return uuid.UUID(user_id) if user_id else None


_orders_controller: OrdersController | None = None


def get_orders_controller() -> OrdersController:
    """Lazily-built singleton so RazorpayService's SDK client isn't re-constructed per request."""
    global _orders_controller
    if _orders_controller is None:
        payment_service = RazorpayService(get_settings())
        handler = OrdersHandler(payment_service)
        _orders_controller = OrdersController(handler)
    return _orders_controller
