import logging
import uuid

from fastapi import HTTPException

from apis.models.inquiries import SupportTicket, TopicRequest
from services.database.postgres.connection import get_session
from utils.pagination import Page, PaginationParams, build_page, paginate

from .inquiries_schema import SupportMessagePayload, TopicRequestListItem, TopicRequestPayload

logger = logging.getLogger(__name__)


def handle_submit_support_message(
    data: SupportMessagePayload, user_id: uuid.UUID | None, ip_address: str | None
) -> None:
    # ip_address is unused here now (rate limiting moved to jwt_middleware).
    session = get_session()
    try:
        ticket = SupportTicket(
            name=data.name,
            message=data.message,
            user_id=user_id,
        )
        ticket.email = data.email
        session.add(ticket)
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
    data: TopicRequestPayload, user_id: uuid.UUID | None, ip_address: str | None
) -> None:
    # ip_address is unused here now (rate limiting moved to jwt_middleware).
    session = get_session()
    try:
        request = TopicRequest(
            name=data.name,
            topic=data.topic,
            domain=data.domain,
            remark=data.remark,
            suggested_expert_name=data.suggestedExpertName,
            suggested_expert_linkedin=data.suggestedExpertLinkedin,
            user_id=user_id,
        )
        request.email = data.email
        session.add(request)
        session.commit()
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        logger.exception("Failed to store topic request")
        raise HTTPException(status_code=500, detail="Internal error") from None
    finally:
        session.close()


def handle_list_my_topic_requests(
    user_id: uuid.UUID, params: PaginationParams, search: str | None
) -> Page:
    session = get_session()
    try:
        query = session.query(TopicRequest).filter(TopicRequest.user_id == user_id)
        if search:
            term = f"%{search}%"
            query = query.filter(
                (TopicRequest.topic.ilike(term)) | (TopicRequest.domain.ilike(term))
            )
        query = query.order_by(TopicRequest.created_at.desc())

        rows, total = paginate(query, params)
        items = [
            TopicRequestListItem(
                id=row.id,
                topic=row.topic,
                domain=row.domain,
                status=row.status,
                createdAt=row.created_at,
            )
            for row in rows
        ]
        return build_page(items, total, params)
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        logger.exception("Failed to list topic requests")
        raise HTTPException(status_code=500, detail="Internal error") from None
    finally:
        session.close()
