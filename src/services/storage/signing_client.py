import logging
import uuid
from urllib.parse import urlparse

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import HTTPException

from config import get_settings

logger = logging.getLogger(__name__)

# Transcript files live under this prefix in the shared Linode bucket. We only ever
# sign keys under it (mirrors the Infollion backend's presigned-GET gate) so a bad or
# crafted URL can't be turned into a signed link to some other object.
_ALLOWED_KEY_PREFIX = "infollion-v2/"

_PRESIGN_EXPIRY_SECONDS = 900

_s3_client = None


def _get_s3_client():
    """Lazily build a boto3 S3 client for Linode Object Storage.

    Mirrors the Infollion backend's aws-sdk setup: v4 signatures, path-style
    addressing, and a custom endpoint. Read-only in this service (get_object only).
    """
    global _s3_client
    if _s3_client is None:
        cfg = get_settings().storage
        _s3_client = boto3.client(
            "s3",
            aws_access_key_id=cfg.access_key,
            aws_secret_access_key=cfg.secret_key,
            region_name=cfg.region or None,
            endpoint_url=cfg.endpoint,
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )
    return _s3_client


def _resolve_object_key(object_url: str | None) -> str | None:
    """Extract the S3 object key from a stored transcript URL.

    Port of the Infollion backend's resolveInfollionKeyFromObjectUrl: accepts either
    path-style (.../<bucket>/<key>) or prefix-style (.../infollion-v2/<key>) URLs,
    restricts to the infollion-v2/ prefix, and blocks path traversal.
    """
    if not object_url or not isinstance(object_url, str):
        return None
    try:
        parsed = urlparse(object_url.strip())
    except Exception:
        return None

    segments = [s for s in parsed.path.split("/") if s]
    if not segments:
        return None

    bucket = get_settings().storage.bucket
    key: str | None = None
    if segments[0] == bucket and len(segments) >= 2:
        key = "/".join(segments[1:])
    elif segments[0] == "infollion-v2":
        key = "/".join(segments)

    if not key or not key.startswith(_ALLOWED_KEY_PREFIX):
        return None
    if any(part in ("..", ".") for part in key.split("/")):
        return None
    return key


def get_signed_url(transcript_id: uuid.UUID, final_transcript: dict) -> str:
    """Mint a short-lived presigned GET URL for a transcript's stored file.

    The file physically lives in the shared Linode bucket (uploaded by the Infollion
    backend under infollion-v2/, private). We sign a temporary read link for it using
    the same bucket credentials - no copy, no re-upload.
    """
    settings = get_settings().storage
    if not settings.is_configured:
        raise HTTPException(status_code=500, detail="Storage is not configured.")

    key = _resolve_object_key((final_transcript or {}).get("url"))
    if not key:
        logger.error("Unresolvable or disallowed transcript object url for %s", transcript_id)
        raise HTTPException(status_code=502, detail="Failed to generate file access link.")

    try:
        return _get_s3_client().generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.bucket, "Key": key},
            ExpiresIn=_PRESIGN_EXPIRY_SECONDS,
        )
    except (BotoCoreError, ClientError):
        logger.exception("Failed to presign transcript %s", transcript_id)
        raise HTTPException(status_code=502, detail="Failed to generate file access link.") from None
