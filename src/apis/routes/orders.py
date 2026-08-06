from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response

from apis.controllers.orders.orders_controller import OrdersController
from apis.controllers.orders.orders_schema import CreateOrderRequest, VerifyPaymentRequest
from apis.dependencies import get_current_user_id, get_orders_controller
from utils.response import success_response

from .paths import P

router = APIRouter(prefix=P.orders.BASE, tags=["Orders"])


@router.post(P.orders.ROOT)
def create_order(
    body: CreateOrderRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    user_id: int = Depends(get_current_user_id),
    controller: OrdersController = Depends(get_orders_controller),
):
    result = controller.create_order(user_id, body, idempotency_key)
    return success_response(data=result)


@router.post(P.orders.VERIFY)
def verify_payment(
    body: VerifyPaymentRequest,
    user_id: int = Depends(get_current_user_id),
    controller: OrdersController = Depends(get_orders_controller),
):
    result = controller.verify_payment(user_id, body)
    return success_response(data=result)


@router.get(P.orders.ROOT)
def list_orders(
    user_id: int = Depends(get_current_user_id),
    controller: OrdersController = Depends(get_orders_controller),
):
    result = controller.list_orders(user_id)
    return success_response(data=result)


@router.get(P.orders.DETAIL)
def get_order(
    order_id: int,
    user_id: int = Depends(get_current_user_id),
    controller: OrdersController = Depends(get_orders_controller),
):
    result = controller.get_order(user_id, order_id)
    return success_response(data=result)


@router.get(P.orders.RECEIPT)
def get_receipt(
    order_id: int,
    user_id: int = Depends(get_current_user_id),
    controller: OrdersController = Depends(get_orders_controller),
):
    pdf_bytes = controller.get_receipt_pdf(user_id, order_id)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="receipt-{order_id}.pdf"'},
    )


@router.post(P.orders.WEBHOOK)
async def payment_webhook(
    gateway: str,
    request: Request,
    controller: OrdersController = Depends(get_orders_controller),
):
    if gateway != "razorpay":
        raise HTTPException(status_code=404, detail="Unknown payment gateway")
    raw_body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")
    event_id = request.headers.get("X-Razorpay-Event-Id", "")
    controller.handle_webhook(raw_body, signature, event_id)
    return success_response(data=None)
