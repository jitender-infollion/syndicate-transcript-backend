from apis.models.author import Author
from apis.models.entitlement import Entitlement, EntitlementStatus
from apis.models.transcript import Transcript

from .transcripts_schema import AuthorSummary, FinalTranscriptRef, TranscriptListItem

# Shared with cart/orders - same slim transcript+author shape used there too.
SLIM_TRANSCRIPT_COLUMNS = (
    Transcript.id,
    Transcript.topic,
    Transcript.domain,
    Transcript.geography,
    Transcript.preview,
    Transcript.final_transcript,
    Transcript.key_insight,
    Transcript.price,
    Transcript.is_active,
    Transcript.published_at,
    Transcript.approved_at,
    Transcript.created_at,
    Author.id,
    Author.name,
    Author.designation,
)


def has_active_entitlement(session, user_id: int | None, transcript_id: int) -> bool:
    if user_id is None:
        return False
    return (
        session.query(Entitlement.id)
        .filter(
            Entitlement.user_id == user_id,
            Entitlement.transcript_id == transcript_id,
            Entitlement.status == EntitlementStatus.ACTIVE.value,
        )
        .first()
        is not None
    )


def row_to_transcript_list_item(row) -> TranscriptListItem:
    (
        transcript_id,
        topic,
        domain,
        geography,
        preview,
        final_transcript,
        key_insight,
        price,
        is_active,
        published_at,
        approved_at,
        created_at,
        author_id,
        author_name,
        author_designation,
    ) = row
    author = (
        AuthorSummary(id=author_id, name=author_name, designation=author_designation) if author_id else None
    )
    final_transcript_ref = (
        FinalTranscriptRef(url=final_transcript["url"], filename=final_transcript["filename"])
        if final_transcript
        else None
    )
    return TranscriptListItem(
        id=transcript_id,
        topic=topic,
        domain=domain or [],
        geography=geography or [],
        preview=preview,
        finalTranscript=final_transcript_ref,
        keyInsight=key_insight or [],
        price=int(price),
        author=author,
        isActive=is_active,
        publishedAt=published_at,
        approvedAt=approved_at,
        createdAt=created_at,
    )
