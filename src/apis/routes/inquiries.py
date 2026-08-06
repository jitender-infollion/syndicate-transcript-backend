from fastapi import APIRouter, Depends, Request

from apis.controllers.inquiries import inquiries_controller
from apis.controllers.inquiries.inquiries_schema import SupportMessagePayload, TopicRequestPayload
from apis.dependencies import get_current_user_id_optional
from utils.response import success_response

from .paths import P

support_router = APIRouter(prefix=P.support.BASE, tags=["Support"])
topics_router = APIRouter(prefix=P.topics.BASE, tags=["Topics"])


def _ip_address(request: Request) -> str | None:
    return request.client.host if request.client else None


@support_router.post(P.support.ROOT)
def submit_support_message(
    body: SupportMessagePayload,
    request: Request,
    user_id: int | None = Depends(get_current_user_id_optional),
):
    inquiries_controller.submit_support_message(body, user_id, _ip_address(request))
    return success_response(message="Your message has been sent.")


@topics_router.post(P.topics.REQUEST)
def submit_topic_request(
    body: TopicRequestPayload,
    request: Request,
    user_id: int | None = Depends(get_current_user_id_optional),
):
    inquiries_controller.submit_topic_request(body, user_id, _ip_address(request))
    return success_response(message="Your topic request has been submitted.")
