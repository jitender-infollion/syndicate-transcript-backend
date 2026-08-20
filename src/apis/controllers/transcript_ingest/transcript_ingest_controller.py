import uuid

from . import transcript_ingest_handler as handler
from .transcript_ingest_schema import TranscriptPublishRequest


def publish_transcript(payload: TranscriptPublishRequest) -> uuid.UUID:
    return handler.handle_publish_transcript(payload)


def set_transcript_active(transcript_id: uuid.UUID, is_active: bool) -> uuid.UUID:
    return handler.handle_set_transcript_active(transcript_id, is_active)
