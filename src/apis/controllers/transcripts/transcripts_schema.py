import uuid
from datetime import datetime

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

from utils.pagination import MAX_PAGE_SIZE


class ExpertSummary(BaseModel):
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
    expert: ExpertSummary | None
    isActive: bool
    publishedAt: datetime | None


class TranscriptDetailResponse(TranscriptListItem):
    pass


class TranscriptAccessResponse(BaseModel):
    url: str


class TranscriptFullTextResponse(BaseModel):
    fullText: str


class TranscriptFilterBoundsResponse(BaseModel):
    minPrice: int | None
    maxPrice: int | None
    minPublishedAt: datetime | None
    maxPublishedAt: datetime | None


class TranscriptFilterRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    # Some callers send the singular "domain" - accepted as an alias so it
    # doesn't silently get dropped (Pydantic ignores unknown keys by default,
    # which previously made this filter a no-op for those callers).
    domains: list[str] | None = Field(
        default=None, validation_alias=AliasChoices("domains", "domain")
    )
    geographies: list[str] | None = None
    topic: str | None = None
    search: str | None = None  # free-text across topic/preview/domains/geographies
    expertId: int | None = None  # fk_expert (external expert-management id) - intentionally not a UUID
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
