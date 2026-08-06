import logging

from fastapi import HTTPException

from apis.models.inquiries import SupportMessage, TopicRequest
from services.database.postgres.connection import get_session
from utils.rate_limiter import check_ip_rate_limit

from .inquiries_schema import SupportMessagePayload, TopicRequestPayload

logger = logging.getLogger(__name__)

# Both endpoints are public (no account needed) - rate limited by IP instead,
# same reasoning as signup. Numbers per the standard contact-form guidance:
# a handful of submissions per IP per 10 minutes is generous for a real
# visitor and tight enough to blunt naive spam/bots.
RATE_LIMIT_SUPPORT_MAX_ATTEMPTS = 5
RATE_LIMIT_SUPPORT_WINDOW_SECONDS = 600

RATE_LIMIT_TOPIC_REQUEST_MAX_ATTEMPTS = 5
RATE_LIMIT_TOPIC_REQUEST_WINDOW_SECONDS = 600


def handle_submit_support_message(
    data: SupportMessagePayload, user_id: int | None, ip_address: str | None
) -> None:
    if ip_address:
        check_ip_rate_limit(f"support:{ip_address}", RATE_LIMIT_SUPPORT_MAX_ATTEMPTS, RATE_LIMIT_SUPPORT_WINDOW_SECONDS)

    session = get_session()
    try:
        session.add(
            SupportMessage(
                name=data.name,
                email=data.email,
                message=data.message,
                user_id=user_id,
                ip_address=ip_address,
            )
        )
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("Failed to store support message")
        raise HTTPException(status_code=500, detail="Internal error") from None
    finally:
        session.close()


def handle_submit_topic_request(
    data: TopicRequestPayload, user_id: int | None, ip_address: str | None
) -> None:
    if ip_address:
        check_ip_rate_limit(
            f"topic_request:{ip_address}", RATE_LIMIT_TOPIC_REQUEST_MAX_ATTEMPTS, RATE_LIMIT_TOPIC_REQUEST_WINDOW_SECONDS
        )

    session = get_session()
    try:
        session.add(
            TopicRequest(
                topic=data.topic,
                domain=data.domain,
                email=data.email,
                remark=data.remark,
                suggested_expert_name=data.suggestedExpertName,
                suggested_expert_linkedin=data.suggestedExpertLinkedin,
                user_id=user_id,
                ip_address=ip_address,
            )
        )
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("Failed to store topic request")
        raise HTTPException(status_code=500, detail="Internal error") from None
    finally:
        session.close()
