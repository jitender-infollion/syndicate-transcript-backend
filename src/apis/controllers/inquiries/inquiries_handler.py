import logging

from fastapi import HTTPException

from apis.models.inquiries import SupportMessage, TopicRequest
from services.database.postgres.connection import get_session
from utils.rate_limiter import RateLimits

from .inquiries_schema import SupportMessagePayload, TopicRequestPayload

logger = logging.getLogger(__name__)


def handle_submit_support_message(
    data: SupportMessagePayload, user_id: int | None, ip_address: str | None
) -> None:
    if ip_address:
        RateLimits.inquiries.SUPPORT_MESSAGE.check(f"support:{ip_address}")

    session = get_session()
    try:
        session.add(
            SupportMessage(
                name=data.name,
                email=data.email,
                message=data.message,
                user_id=user_id,
            )
        )
        session.commit()
    except HTTPException:
        raise
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
        RateLimits.inquiries.TOPIC_REQUEST.check(f"topic_request:{ip_address}")

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
            )
        )
        session.commit()
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        logger.exception("Failed to store topic request")
        raise HTTPException(status_code=500, detail="Internal error") from None
    finally:
        session.close()
