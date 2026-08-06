from .inquiries_handler import handle_submit_support_message, handle_submit_topic_request
from .inquiries_schema import SupportMessagePayload, TopicRequestPayload


def submit_support_message(data: SupportMessagePayload, user_id: int | None, ip_address: str | None) -> None:
    handle_submit_support_message(data, user_id, ip_address)


def submit_topic_request(data: TopicRequestPayload, user_id: int | None, ip_address: str | None) -> None:
    handle_submit_topic_request(data, user_id, ip_address)
