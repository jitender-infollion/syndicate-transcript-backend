from pydantic import BaseModel

from apis.controllers.transcripts.transcripts_schema import TranscriptListItem


class CartResponse(BaseModel):
    items: list[TranscriptListItem]


class AddCartItemRequest(BaseModel):
    transcriptId: int


class MergeCartRequest(BaseModel):
    items: list[int] = []
