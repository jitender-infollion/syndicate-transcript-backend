import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from utils.pagination import MAX_PAGE_SIZE


class AuthorSummary(BaseModel):
    # id is fk_expert - an id from the separate external expert-management system,
    # not a local UUID primary key. Intentionally left as int (see Transcript.fk_expert).
    id: int
    name: str | None
    designation: str | None
    yearsOfExperience: int | None


class TranscriptListItem(BaseModel):
    id: uuid.UUID
    topic: str | None
    domains: list[str]
    geographies: list[str]
    preview: str | None
    keyInsights: list[str]
    price: int
    author: AuthorSummary | None
    isActive: bool
    publishedAt: datetime | None


class TranscriptDetailResponse(TranscriptListItem):
    pass


class TranscriptAccessResponse(BaseModel):
    url: str


class TranscriptFullTextResponse(BaseModel):
    fullText: str


class TranscriptFilterRequest(BaseModel):
    domains: list[str] | None = None
    geographies: list[str] | None = None
    topic: str | None = None
    search: str | None = None  # free-text across topic/preview/domains/geographies
    authorId: int | None = None  # fk_expert (external expert-management id) - intentionally not a UUID
    minPrice: int | None = None
    maxPrice: int | None = None
    publishedAfter: datetime | None = None
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1)

    @field_validator("limit")
    @classmethod
    def _cap_limit(cls, v: int) -> int:
        # Capped rather than rejected - a client asking for 5000 just gets MAX_PAGE_SIZE back.
        return min(v, MAX_PAGE_SIZE)
