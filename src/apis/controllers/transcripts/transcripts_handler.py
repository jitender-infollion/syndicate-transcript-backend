import logging
import uuid
from dataclasses import dataclass
from typing import Literal

from fastapi import HTTPException
from sqlalchemy import String, case, cast, desc, func, literal, literal_column, or_

from apis.models.order import Order, OrderItem, OrderStatus
from apis.models.transcript import Transcript, TranscriptFilterBounds
from config import get_settings
from services.database.postgres.connection import get_session
from services.storage.signing_client import get_signed_url
from services.transcript_pdf import generate_transcript_pdf
from utils.pagination import Page, PaginationParams, build_page, paginate

from .transcripts_helper import SLIM_TRANSCRIPT_COLUMNS, has_transcript_access, row_to_transcript_list_item
from .transcripts_schema import (
    TranscriptAccessResponse,
    TranscriptDetailResponse,
    TranscriptFilterBoundsResponse,
    TranscriptFilterRequest,
    TranscriptFullTextResponse,
    TranscriptListItem,
)

logger = logging.getLogger(__name__)


def handle_list_transcripts(
    params: PaginationParams, domains: str | None = None, geographies: str | None = None
) -> Page:
    session = get_session()
    try:
        query = session.query(*SLIM_TRANSCRIPT_COLUMNS).filter(Transcript.is_active.is_(True))
        if domains:
            query = query.filter(Transcript.domains.contains([domains]))
        if geographies:
            query = query.filter(Transcript.geographies.contains([geographies]))
        query = query.order_by(Transcript.published_at.desc())

        rows, total = paginate(query, params)
        items = [row_to_transcript_list_item(row) for row in rows]
        return build_page(items, total, params)
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        logger.exception("Failed to list transcripts")
        raise HTTPException(status_code=500, detail="Internal error") from None
    finally:
        session.close()


def handle_filter_transcripts(filters: TranscriptFilterRequest) -> Page:
    session = get_session()
    try:
        query = session.query(*SLIM_TRANSCRIPT_COLUMNS).filter(Transcript.is_active.is_(True))
        if filters.domains:
            query = query.filter(Transcript.domains.overlap(filters.domains))
        if filters.geographies:
            query = query.filter(Transcript.geographies.overlap(filters.geographies))
        if filters.topic:
            query = query.filter(Transcript.topic.ilike(f"%{filters.topic}%"))
        if filters.search:
            term = f"%{filters.search}%"
            query = query.filter(
                or_(
                    Transcript.topic.ilike(term),
                    Transcript.preview.ilike(term),
                    cast(Transcript.domains, String).ilike(term),
                    cast(Transcript.geographies, String).ilike(term),
                )
            )
        if filters.expertId is not None:
            query = query.filter(Transcript.fk_expert == filters.expertId)
        if filters.minPrice is not None:
            query = query.filter(Transcript.price >= filters.minPrice)
        if filters.maxPrice is not None:
            query = query.filter(Transcript.price <= filters.maxPrice)
        if filters.publishedAfter is not None:
            query = query.filter(Transcript.published_at >= filters.publishedAfter)
        query = query.order_by(Transcript.published_at.desc())

        params = PaginationParams(page=filters.page, limit=filters.limit)
        rows, total = paginate(query, params)
        items = [row_to_transcript_list_item(row) for row in rows]
        return build_page(items, total, params)
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        logger.exception("Failed to filter transcripts")
        raise HTTPException(status_code=500, detail="Internal error") from None
    finally:
        session.close()


def handle_list_purchased_transcripts(user_id: uuid.UUID, params: PaginationParams) -> Page:
    session = get_session()
    try:
        query = (
            session.query(*SLIM_TRANSCRIPT_COLUMNS)
            .join(OrderItem, OrderItem.transcript_id == Transcript.id)
            .join(Order, Order.id == OrderItem.order_id)
            .filter(
                OrderItem.user_id == user_id,
                OrderItem.access_permission.is_(False),
                Order.status == OrderStatus.PAID.value,
            )
            .distinct()
            .order_by(Transcript.published_at.desc())
        )
        rows, total = paginate(query, params)
        items = [row_to_transcript_list_item(row) for row in rows]
        return build_page(items, total, params)
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        logger.exception("Failed to list purchased transcripts")
        raise HTTPException(status_code=500, detail="Internal error") from None
    finally:
        session.close()


def handle_list_domains() -> list[str]:
    session = get_session()
    try:
        unnested = func.unnest(Transcript.domains).label("domain")
        rows = (
            session.query(unnested)
            .filter(Transcript.is_active.is_(True), Transcript.domains.isnot(None))
            .distinct()
            .order_by(unnested)
            .all()
        )
        return [row[0] for row in rows]
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        logger.exception("Failed to list transcript domains")
        raise HTTPException(status_code=500, detail="Internal error") from None
    finally:
        session.close()


def handle_get_filter_bounds() -> TranscriptFilterBoundsResponse:
    # Read from the pre-computed table (kept in sync by a DB trigger) rather than
    # aggregating transcripts directly, so this stays a cheap single-row lookup.
    session = get_session()
    try:
        bounds = session.query(TranscriptFilterBounds).get(1)
        return TranscriptFilterBoundsResponse(
            minPrice=bounds.min_price if bounds else None,
            maxPrice=bounds.max_price if bounds else None,
            minPublishedAt=bounds.min_published_at if bounds else None,
            maxPublishedAt=bounds.max_published_at if bounds else None,
        )
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        logger.exception("Failed to fetch transcript filter bounds")
        raise HTTPException(status_code=500, detail="Internal error") from None
    finally:
        session.close()


def handle_get_transcript_detail(transcript_id: uuid.UUID) -> TranscriptDetailResponse:
    session = get_session()
    try:
        row = (
            session.query(*SLIM_TRANSCRIPT_COLUMNS)
            .filter(Transcript.id == transcript_id, Transcript.is_active.is_(True))
            .first()
        )
        if not row:
            raise HTTPException(status_code=404, detail="Transcript not found")

        item = row_to_transcript_list_item(row)
        return TranscriptDetailResponse(**item.model_dump())
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        logger.exception("Failed to fetch transcript detail")
        raise HTTPException(status_code=500, detail="Internal error") from None
    finally:
        session.close()


def handle_get_similar_transcripts(transcript_id: uuid.UUID, limit: int = 3) -> list[TranscriptListItem]:
    session = get_session()
    try:
        source = (
            session.query(Transcript.domains, Transcript.preview)
            .filter(Transcript.id == transcript_id, Transcript.is_active.is_(True))
            .first()
        )
        if not source:
            raise HTTPException(status_code=404, detail="Transcript not found")
        source_domains, source_preview = source

        query = session.query(*SLIM_TRANSCRIPT_COLUMNS).filter(
            Transcript.is_active.is_(True),
            Transcript.id != transcript_id,
        )

        # Two independent similarity signals, both optional since either field
        # can be missing on a given transcript - rank by whichever data is
        # available rather than requiring both (which would too often leave
        # nothing to show).
        if source_domains:
            domain_match = case((Transcript.domains.overlap(source_domains), 1), else_=0)
        else:
            domain_match = literal(0)

        if source_preview:
            # regconfig args passed as literal SQL, not bound params - Postgres
            # only auto-casts an untyped literal to regconfig, not a bound text
            # param, so binding "english" here would raise at query time.
            english = literal_column("'english'")
            preview_rank = func.ts_rank_cd(
                func.to_tsvector(english, func.coalesce(Transcript.preview, "")),
                func.plainto_tsquery(english, source_preview),
            )
        else:
            preview_rank = literal(0.0)

        rows = (
            query.order_by(desc(domain_match), desc(preview_rank), Transcript.published_at.desc())
            .limit(limit)
            .all()
        )
        return [row_to_transcript_list_item(row) for row in rows]
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        logger.exception("Failed to fetch similar transcripts for %s", transcript_id)
        raise HTTPException(status_code=500, detail="Internal error") from None
    finally:
        session.close()


def handle_get_transcript_access(
    user_id: uuid.UUID, transcript_id: uuid.UUID, mode: Literal["view", "download"]
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

        if not has_transcript_access(session, user_id, transcript_id):
            raise HTTPException(status_code=403, detail="You do not have access to this transcript.")

        if not transcript.final_transcript:
            raise HTTPException(status_code=404, detail="No file available for this transcript.")

        if not get_settings().signing_service.is_configured:
            raise HTTPException(status_code=503, detail="Transcript view is not available right now.")

        url = get_signed_url(transcript_id, transcript.final_transcript)
        return TranscriptAccessResponse(url=url)
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        logger.exception("Failed to generate %s link for transcript", mode)
        raise HTTPException(status_code=500, detail="Internal error") from None
    finally:
        session.close()


def _build_dev_full_text(transcript: Transcript) -> str:
    # No real extracted transcript body exists yet - assembled from preview/key_insight.
    lines = [transcript.topic or "Untitled transcript", ""]
    if transcript.preview:
        lines.append(transcript.preview)
        lines.append("")
    if transcript.key_insights:
        lines.append("Key insights covered:")
        lines.extend(f"- {insight}" for insight in transcript.key_insights)
        lines.append("")
    lines.append(
        "[Dev placeholder: this environment has no stored full transcript body yet - "
        "the text above is assembled from the preview and key-insight fields. Replace "
        "this with the real extracted transcript text before shipping.]"
    )
    return "\n".join(lines)


def handle_get_full_text(user_id: uuid.UUID, transcript_id: uuid.UUID) -> TranscriptFullTextResponse:
    session = get_session()
    try:
        transcript = (
            session.query(Transcript)
            .filter(Transcript.id == transcript_id, Transcript.is_active.is_(True))
            .first()
        )
        if not transcript:
            raise HTTPException(status_code=404, detail="Transcript not found")

        if not has_transcript_access(session, user_id, transcript_id):
            raise HTTPException(status_code=403, detail="You do not have access to this transcript.")

        return TranscriptFullTextResponse(fullText=_build_dev_full_text(transcript))
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        logger.exception("Failed to build full text for transcript %s", transcript_id)
        raise HTTPException(status_code=500, detail="Internal error") from None
    finally:
        session.close()


@dataclass
class DownloadResult:
    # Exactly one is set. redirect_url: 307s straight to storage, no file bytes
    # through this server - needs the bucket's CORS to allow the frontend origin.
    redirect_url: str | None = None
    pdf_bytes: bytes | None = None


def handle_download_transcript(user_id: uuid.UUID, transcript_id: uuid.UUID) -> DownloadResult:
    session = get_session()
    try:
        transcript = (
            session.query(Transcript)
            .filter(Transcript.id == transcript_id, Transcript.is_active.is_(True))
            .first()
        )
        if not transcript:
            raise HTTPException(status_code=404, detail="Transcript not found")

        if not has_transcript_access(session, user_id, transcript_id):
            raise HTTPException(status_code=403, detail="You do not have access to this transcript.")

        if get_settings().signing_service.is_configured and transcript.final_transcript:
            url = get_signed_url(transcript_id, transcript.final_transcript)
            return DownloadResult(redirect_url=url)

        # Dev fallback until the signing service is configured.
        full_text = _build_dev_full_text(transcript)
        return DownloadResult(pdf_bytes=generate_transcript_pdf(transcript, full_text))
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        logger.exception("Failed to generate download for transcript %s", transcript_id)
        raise HTTPException(status_code=500, detail="Internal error") from None
    finally:
        session.close()
