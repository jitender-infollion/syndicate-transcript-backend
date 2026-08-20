import logging
import uuid

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert

from apis.models.transcript import Transcript
from services.database.postgres.connection import get_session

from .transcript_ingest_schema import TranscriptPublishRequest

logger = logging.getLogger(__name__)


def handle_publish_transcript(payload: TranscriptPublishRequest) -> uuid.UUID:
    """Create or update a transcript from the Infollion backend, keyed on fk_session.

    Idempotent: INSERT ... ON CONFLICT (fk_session) DO UPDATE. A re-publish updates
    the same row and returns the same id. published_at is set once (on first insert)
    and left untouched on update; updated_at is refreshed each time.
    """
    session = get_session()
    try:
        insert_values = {
            "fk_session": payload.fk_session,
            "fk_expert": payload.fk_expert,
            "expert_name": payload.expert_name,
            "designation": payload.designation,
            "years_of_experience": payload.years_of_experience,
            "topic": payload.topic,
            "domains": payload.domains,
            "geographies": payload.geographies,
            "preview": payload.preview,
            "final_transcript": payload.final_transcript.model_dump(),
            "key_insights": payload.key_insights,
            "price": payload.price,
            "currency": payload.currency,
            "is_active": payload.is_active,
            "updated_at": func.now(),
        }

        stmt = pg_insert(Transcript).values(**insert_values)
        # On conflict, refresh every field except the conflict key (fk_session).
        # published_at is intentionally excluded so it keeps the first-publish time.
        update_set = {col: getattr(stmt.excluded, col) for col in insert_values if col != "fk_session"}
        stmt = stmt.on_conflict_do_update(
            index_elements=["fk_session"],
            set_=update_set,
        ).returning(Transcript.id)

        transcript_id = session.execute(stmt).scalar_one()
        session.commit()
        return transcript_id
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        logger.exception("Failed to publish transcript from Infollion (fk_session=%s)", payload.fk_session)
        raise HTTPException(status_code=500, detail="Failed to store transcript.") from None
    finally:
        session.close()


def handle_set_transcript_active(transcript_id: uuid.UUID, is_active: bool) -> uuid.UUID:
    """Toggle a transcript's is_active flag (unpublish → False). 404 if it doesn't exist."""
    session = get_session()
    try:
        updated = (
            session.query(Transcript)
            .filter(Transcript.id == transcript_id)
            .update({Transcript.is_active: is_active, Transcript.updated_at: func.now()}, synchronize_session=False)
        )
        if updated == 0:
            raise HTTPException(status_code=404, detail="Transcript not found.")
        session.commit()
        return transcript_id
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        logger.exception("Failed to update transcript active flag (id=%s)", transcript_id)
        raise HTTPException(status_code=500, detail="Failed to update transcript.") from None
    finally:
        session.close()
