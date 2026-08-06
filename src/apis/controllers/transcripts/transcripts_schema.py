from datetime import datetime

from pydantic import BaseModel, Field


class AuthorSummary(BaseModel):
    id: int
    name: str | None
    designation: str | None


class FinalTranscriptRef(BaseModel):
    url: str
    filename: str


class TranscriptListItem(BaseModel):
    id: int
    topic: str | None
    domain: list[str]
    geography: list[str]
    preview: str | None
    finalTranscript: FinalTranscriptRef | None
    keyInsight: list[str]
    price: int
    author: AuthorSummary | None
    isActive: bool
    publishedAt: datetime | None
    approvedAt: datetime | None
    createdAt: datetime | None


class TranscriptDetailResponse(BaseModel):
    id: int
    topic: str | None
    domain: list[str]
    geography: list[str]
    preview: str | None
    finalTranscript: FinalTranscriptRef | None
    keyInsight: list[str]
    price: int
    author: AuthorSummary | None
    isActive: bool
    publishedAt: datetime | None
    approvedAt: datetime | None
    createdAt: datetime | None


class TranscriptAccessResponse(BaseModel):
    url: str


class TranscriptFullTextResponse(BaseModel):
    fullText: str


class TranscriptFilterRequest(BaseModel):
    domain: list[str] | None = None
    geography: list[str] | None = None
    topic: str | None = None
    # Free-text search across topic, preview, domain, and geography - what
    # the main search bar sends, as opposed to `topic`'s narrower exact-field
    # match (used by structured/programmatic filtering).
    search: str | None = None
    authorId: int | None = None
    minPrice: int | None = None
    maxPrice: int | None = None
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=100)
