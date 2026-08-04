import logging
from typing import Literal

from fastapi import HTTPException
from sqlalchemy import func

from apis.models.author import Author
from apis.models.entitlement import Entitlement, EntitlementStatus
from apis.models.transcript import Transcript
from services.database.postgres.connection import get_session
from services.storage.signing_client import get_signed_url
from utils.pagination import Page, PaginationParams, build_page, paginate

from .transcripts_schema import (
    AuthorSummary,
    FinalTranscriptRef,
    TranscriptAccessResponse,
    TranscriptDetailResponse,
    TranscriptFilterRequest,
    TranscriptListItem,
)

logger = logging.getLogger(__name__)

_SLIM_COLUMNS = (
    Transcript.id,
    Transcript.topic,
    Transcript.domain,
    Transcript.geography,
    Transcript.preview,
    Transcript.final_transcript,
    Transcript.key_insight,
    Transcript.price,
    Transcript.is_active,
    Transcript.published_at,
    Transcript.approved_at,
    Transcript.created_at,
    Author.id,
    Author.name,
    Author.designation,
)


def _has_active_entitlement(session, user_id: int | None, transcript_id: int) -> bool:
    if user_id is None:
        return False
    return (
        session.query(Entitlement.id)
        .filter(
            Entitlement.user_id == user_id,
            Entitlement.transcript_id == transcript_id,
            Entitlement.status == EntitlementStatus.ACTIVE.value,
        )
        .first()
        is not None
    )


def _row_to_list_item(row) -> TranscriptListItem:
    (
        transcript_id,
        topic,
        domain,
        geography,
        preview,
        final_transcript,
        key_insight,
        price,
        is_active,
        published_at,
        approved_at,
        created_at,
        author_id,
        author_name,
        author_designation,
    ) = row
    author = (
        AuthorSummary(id=author_id, name=author_name, designation=author_designation) if author_id else None
    )
    final_transcript_ref = (
        FinalTranscriptRef(url=final_transcript["url"], filename=final_transcript["filename"])
        if final_transcript
        else None
    )
    return TranscriptListItem(
        id=transcript_id,
        topic=topic,
        domain=domain or [],
        geography=geography or [],
        preview=preview,
        finalTranscript=final_transcript_ref,
        keyInsight=key_insight or [],
        price=int(price),
        author=author,
        isActive=is_active,
        publishedAt=published_at,
        approvedAt=approved_at,
        createdAt=created_at,
    )


def handle_list_transcripts(
    params: PaginationParams, domain: str | None = None, geography: str | None = None
) -> Page:
    session = get_session()
    try:
        query = (
            session.query(*_SLIM_COLUMNS)
            .join(Author, Transcript.author_id == Author.id)
            .filter(Transcript.is_active.is_(True))
        )
        if domain:
            query = query.filter(Transcript.domain.contains([domain]))
        if geography:
            query = query.filter(Transcript.geography.contains([geography]))
        query = query.order_by(Transcript.published_at.desc())

        rows, total = paginate(query, params)
        items = [_row_to_list_item(row) for row in rows]
        return build_page(items, total, params)
    except Exception:
        logger.exception("Failed to list transcripts")
        raise HTTPException(status_code=500, detail="Internal error") from None
    finally:
        session.close()


def handle_filter_transcripts(filters: TranscriptFilterRequest) -> Page:
    session = get_session()
    try:
        query = (
            session.query(*_SLIM_COLUMNS)
            .join(Author, Transcript.author_id == Author.id)
            .filter(Transcript.is_active.is_(True))
        )
        if filters.domain:
            query = query.filter(Transcript.domain.overlap(filters.domain))
        if filters.geography:
            query = query.filter(Transcript.geography.overlap(filters.geography))
        if filters.topic:
            query = query.filter(Transcript.topic.ilike(f"%{filters.topic}%"))
        if filters.authorId is not None:
            query = query.filter(Transcript.author_id == filters.authorId)
        if filters.minPrice is not None:
            query = query.filter(Transcript.price >= filters.minPrice)
        if filters.maxPrice is not None:
            query = query.filter(Transcript.price <= filters.maxPrice)
        query = query.order_by(Transcript.published_at.desc())

        params = PaginationParams(page=filters.page, limit=filters.limit)
        rows, total = paginate(query, params)
        items = [_row_to_list_item(row) for row in rows]
        return build_page(items, total, params)
    except Exception:
        logger.exception("Failed to filter transcripts")
        raise HTTPException(status_code=500, detail="Internal error") from None
    finally:
        session.close()


def handle_list_purchased_transcripts(user_id: int, params: PaginationParams) -> Page:
    session = get_session()
    try:
        query = (
            session.query(*_SLIM_COLUMNS)
            .join(Author, Transcript.author_id == Author.id)
            .join(Entitlement, Entitlement.transcript_id == Transcript.id)
            .filter(
                Entitlement.user_id == user_id,
                Entitlement.status == EntitlementStatus.ACTIVE.value,
            )
            .order_by(Transcript.published_at.desc())
        )
        rows, total = paginate(query, params)
        items = [_row_to_list_item(row) for row in rows]
        return build_page(items, total, params)
    except Exception:
        logger.exception("Failed to list purchased transcripts")
        raise HTTPException(status_code=500, detail="Internal error") from None
    finally:
        session.close()


def handle_list_domains() -> list[str]:
    session = get_session()
    try:
        unnested = func.unnest(Transcript.domain).label("domain")
        rows = (
            session.query(unnested)
            .filter(Transcript.is_active.is_(True), Transcript.domain.isnot(None))
            .distinct()
            .order_by(unnested)
            .all()
        )
        return [row[0] for row in rows]
    except Exception:
        logger.exception("Failed to list transcript domains")
        raise HTTPException(status_code=500, detail="Internal error") from None
    finally:
        session.close()


def handle_get_transcript_detail(transcript_id: int) -> TranscriptDetailResponse:
    session = get_session()
    try:
        row = (
            session.query(*_SLIM_COLUMNS)
            .join(Author, Transcript.author_id == Author.id)
            .filter(Transcript.id == transcript_id, Transcript.is_active.is_(True))
            .first()
        )
        if not row:
            raise HTTPException(status_code=404, detail="Transcript not found")

        item = _row_to_list_item(row)
        return TranscriptDetailResponse(**item.model_dump())
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to fetch transcript detail")
        raise HTTPException(status_code=500, detail="Internal error") from None
    finally:
        session.close()


def handle_get_transcript_access(
    user_id: int, transcript_id: int, mode: Literal["view", "download"]
) -> TranscriptAccessResponse:
    session = get_session()
    try:
        transcript = (
            session.query(Transcript)
            .filter(Transcript.id == transcript_id, Transcript.is_active.is_(True))
            .first()
        )
        if not transcript:
            raise HTTPException(status_code=404, detail="Transcript not found")

        if not _has_active_entitlement(session, user_id, transcript_id):
            raise HTTPException(status_code=403, detail="You do not have access to this transcript.")

        if not transcript.final_transcript:
            raise HTTPException(status_code=404, detail="No file available for this transcript.")

        # TODO: uncomment once the signing-service backend is ready (endpoint
        # URL / auth header format still TBD - see SIGNING_SERVICE_URL /
        # SIGNING_SERVICE_API_KEY in env.example).
        # url = get_signed_url(transcript_id, transcript.final_transcript)
        raise HTTPException(status_code=501, detail="Transcript view/download is not available yet.")
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to generate %s link for transcript", mode)
        raise HTTPException(status_code=500, detail="Internal error") from None
    finally:
        session.close()
