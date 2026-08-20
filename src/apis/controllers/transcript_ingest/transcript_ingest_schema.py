"""Request schemas for the Infollion transcript-ingest endpoints.

Field names are snake_case to match the JSON the Infollion backend sends verbatim
(see infollionbefork services/syndicate-platform/syndicate-platform.service.ts).
"""
from pydantic import BaseModel, Field


class FinalTranscript(BaseModel):
    url: str
    type: str = "pdf"


class TranscriptPublishRequest(BaseModel):
    fk_session: int
    fk_expert: int
    expert_name: str | None = None
    designation: str | None = None
    years_of_experience: int | None = None
    topic: str | None = None
    domains: list[str] = Field(default_factory=list)
    geographies: list[str] = Field(default_factory=list)
    preview: str
    final_transcript: FinalTranscript
    key_insights: list[str] = Field(default_factory=list)
    price: int
    currency: str = "INR"
    is_active: bool = True


class TranscriptActiveUpdateRequest(BaseModel):
    is_active: bool
