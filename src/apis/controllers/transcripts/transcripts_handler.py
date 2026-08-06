import logging
from dataclasses import dataclass
from typing import Literal

from fastapi import HTTPException
from sqlalchemy import String, cast, func, or_

from apis.models.author import Author
from apis.models.entitlement import Entitlement, EntitlementStatus
from apis.models.transcript import Transcript
from config import get_settings
from services.database.postgres.connection import get_session
from services.storage.signing_client import get_signed_url
from services.transcript_pdf import generate_transcript_pdf
from utils.pagination import Page, PaginationParams, build_page, paginate

from .transcripts_schema import (
    AuthorSummary,
    FinalTranscriptRef,
    TranscriptAccessResponse,
    TranscriptDetailResponse,
    TranscriptFilterRequest,
    TranscriptFullTextResponse,
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
        if filters.search:
            term = f"%{filters.search}%"
            query = query.filter(
                or_(
                    Transcript.topic.ilike(term),
                    Transcript.preview.ilike(term),
                    cast(Transcript.domain, String).ilike(term),
                    cast(Transcript.geography, String).ilike(term),
                )
            )
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


def _build_dev_full_text(transcript: Transcript) -> str:
    """Assembled from fields that actually exist (preview/key_insight) - there's
    no real extracted transcript body stored anywhere yet. Replace this with a
    real full-text source once one exists; callers only depend on getting a
    non-empty string back, not on how it was produced.
    """
    lines = [transcript.topic or "Untitled transcript", ""]
    if transcript.preview:
        lines.append(transcript.preview)
        lines.append("")
    if transcript.key_insight:
        lines.append("Key insights covered:")
        lines.extend(f"- {insight}" for insight in transcript.key_insight)
        lines.append("")
    lines.append(
        "[Dev placeholder: this environment has no stored full transcript body yet - "
        "the text above is assembled from the preview and key-insight fields. Replace "
        "this with the real extracted transcript text before shipping.]"
    )
    return "\n".join(lines)


def handle_get_full_text(user_id: int, transcript_id: int) -> TranscriptFullTextResponse:
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

        return TranscriptFullTextResponse(fullText=_build_dev_full_text(transcript))
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to build full text for transcript %s", transcript_id)
        raise HTTPException(status_code=500, detail="Internal error") from None
    finally:
        session.close()


@dataclass
class DownloadResult:
    # Exactly one of these is set. redirect_url: the route 307s the browser
    # straight to storage - no file bytes ever pass through this server, so
    # this endpoint's own load/bandwidth stays flat regardless of file size or
    # download volume. Requires the storage bucket's CORS policy to allow the
    # frontend origin, since the browser's fetch() reads the redirected
    # response directly from a different origin.
    redirect_url: str | None = None
    pdf_bytes: bytes | None = None


def handle_download_transcript(user_id: int, transcript_id: int) -> DownloadResult:
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

        if get_settings().signing_service.is_configured and transcript.final_transcript:
            url = get_signed_url(transcript_id, transcript.final_transcript)
            return DownloadResult(redirect_url=url)

        # Dev fallback: generate a placeholder PDF from available fields -
        # there's no real file to redirect to until the signing service above
        # is actually configured.
        full_text = _build_dev_full_text(transcript)
        return DownloadResult(pdf_bytes=generate_transcript_pdf(transcript, full_text))
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to generate download for transcript %s", transcript_id)
        raise HTTPException(status_code=500, detail="Internal error") from None
    finally:
        session.close()
