"""add preview tsvector index for similar transcripts

Revision ID: df3b7e404367
Revises: 57764dd8f63c
Create Date: 2026-08-19 00:00:00.000000

/similar (handle_get_similar_transcripts) ranks every active transcript
against an arbitrary per-request source preview, recomputing
to_tsvector('english', preview) from scratch for every row on every call -
this index lets Postgres reuse a precomputed tsvector per row instead.
Same IMMUTABLE constraint as migration 636c03a87feb: to_tsvector(regconfig,
text) is only STABLE, so it's wrapped in a SQL function declared IMMUTABLE
(safe - the config is always the "english" literal).
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'df3b7e404367'
down_revision: Union[str, None] = '57764dd8f63c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION transcript_preview_tsvector(preview text) RETURNS tsvector AS $$
            SELECT to_tsvector('english', coalesce(preview, ''))
        $$ LANGUAGE sql IMMUTABLE;
        """
    )
    op.execute(
        "CREATE INDEX ix_transcripts_preview_tsv ON transcripts USING gin (transcript_preview_tsvector(preview))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_transcripts_preview_tsv")
    op.execute("DROP FUNCTION IF EXISTS transcript_preview_tsvector(text)")
