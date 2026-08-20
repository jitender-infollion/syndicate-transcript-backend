"""Server-to-server transcript ingest from the Infollion backend.

Distinct from the public storefront transcripts router: authenticated with a shared
`x-api-key` secret (not JWT), and reachable at /api/internal/transcripts.

These endpoints return a top-level { success, id, message } envelope (NOT the house
{ success, message, data } shape) because that is the exact contract the Infollion
client reads (infollionbefork services/syndicate-platform/syndicate-platform.service.ts).
"""
import uuid

from fastapi import APIRouter, Depends

from apis.controllers.transcript_ingest import transcript_ingest_controller as controller
from apis.controllers.transcript_ingest.transcript_ingest_schema import (
    TranscriptActiveUpdateRequest,
    TranscriptPublishRequest,
)
from apis.dependencies import verify_ingest_api_key

from .paths import P

router = APIRouter(
    prefix=P.transcript_ingest.BASE,
    tags=["Transcript Ingest (internal)"],
    dependencies=[Depends(verify_ingest_api_key)],
)


@router.post(P.transcript_ingest.PUBLISH)
def publish_transcript(payload: TranscriptPublishRequest) -> dict:
    transcript_id = controller.publish_transcript(payload)
    return {"success": True, "id": str(transcript_id), "message": "Transcript published."}


@router.patch(P.transcript_ingest.DETAIL)
def update_transcript_active(transcript_id: uuid.UUID, payload: TranscriptActiveUpdateRequest) -> dict:
    controller.set_transcript_active(transcript_id, payload.is_active)
    message = "Transcript published." if payload.is_active else "Transcript unpublished."
    return {"success": True, "id": str(transcript_id), "message": message}
