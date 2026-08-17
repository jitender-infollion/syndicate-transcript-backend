import uuid

from utils.pagination import PaginationParams

from . import transcripts_handler as handler
from .transcripts_handler import DownloadResult
from .transcripts_schema import (
    TranscriptAccessResponse,
    TranscriptDetailResponse,
    TranscriptFilterRequest,
    TranscriptFullTextResponse,
)


def list_transcripts(params: PaginationParams, domains: str | None = None, geographies: str | None = None):
    return handler.handle_list_transcripts(params, domains, geographies)


def filter_transcripts(filters: TranscriptFilterRequest):
    return handler.handle_filter_transcripts(filters)


def list_purchased_transcripts(user_id: uuid.UUID, params: PaginationParams):
    return handler.handle_list_purchased_transcripts(user_id, params)


def list_domains() -> list[str]:
    return handler.handle_list_domains()


def get_transcript_detail(transcript_id: uuid.UUID) -> TranscriptDetailResponse:
    return handler.handle_get_transcript_detail(transcript_id)


def get_transcript_access(user_id: uuid.UUID, transcript_id: uuid.UUID, mode: str) -> TranscriptAccessResponse:
    return handler.handle_get_transcript_access(user_id, transcript_id, mode)


def get_full_text(user_id: uuid.UUID, transcript_id: uuid.UUID) -> TranscriptFullTextResponse:
    return handler.handle_get_full_text(user_id, transcript_id)


def download_transcript(user_id: uuid.UUID, transcript_id: uuid.UUID) -> DownloadResult:
    return handler.handle_download_transcript(user_id, transcript_id)
