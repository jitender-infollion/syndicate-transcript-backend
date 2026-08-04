import logging

import httpx
from fastapi import HTTPException

from config import get_settings

logger = logging.getLogger(__name__)


def get_signed_url(transcript_id: int, final_transcript: dict) -> str:
    """Ask the external signing service for a fresh presigned URL for this transcript's file.

    Endpoint path and auth header format are placeholders (TBD) pending that
    service's real contract - this posts the whole config.base_url as the
    endpoint for now.
    """
    settings = get_settings().signing_service
    if not settings.is_configured:
        raise HTTPException(status_code=500, detail="Signing service is not configured.")

    try:
        response = httpx.post(
            settings.base_url,
            json={"transcript_id": transcript_id, "final_transcript": final_transcript},
            headers={"Authorization": f"Bearer {settings.api_key}"},
            timeout=10,
        )
        response.raise_for_status()
        body = response.json()
    except Exception:
        logger.exception("Failed to fetch signed URL for transcript %s", transcript_id)
        raise HTTPException(status_code=502, detail="Failed to generate file access link.") from None

    url = body.get("data")
    if not url:
        logger.error("Signing service returned no url for transcript %s: %s", transcript_id, body)
        raise HTTPException(status_code=502, detail="Failed to generate file access link.")
    return url
