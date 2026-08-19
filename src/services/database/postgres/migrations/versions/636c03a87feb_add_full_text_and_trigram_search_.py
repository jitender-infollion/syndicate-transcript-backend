"""add full text and trigram search indexes to transcripts

Revision ID: 636c03a87feb
Revises: ce5614d07d2d
Create Date: 2026-08-19 00:00:00.000000

Backs the transcript search endpoint's move from a plain ILIKE substring
scan to ranked full-text search (topic/expert_name/designation/preview/
domains/geographies, weighted) plus trigram similarity as a typo-tolerant
fallback on topic/expert_name. Both index types are query-time helpers
only - no new columns, so nothing to backfill.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '636c03a87feb'
down_revision: Union[str, None] = 'ce5614d07d2d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # to_tsvector(regconfig, text) is only STABLE, not IMMUTABLE (Postgres can't
    # prove the "english" config never changes), so it can't be used directly
    # in an index expression. Wrapping it in a SQL function we declare IMMUTABLE
    # ourselves - safe since we always pass the "english" literal - unblocks
    # that, and doubles as the single definition transcripts_handler.py calls
    # via func.transcripts_search_vector(...), so the index and the query can
    # never drift apart.
    op.execute(
        """
        CREATE FUNCTION transcripts_search_vector(
            topic text, expert_name text, preview text, designation text,
            domains text[], geographies text[]
        ) RETURNS tsvector AS $$
            SELECT
                setweight(to_tsvector('english', coalesce(topic, '')), 'A') ||
                setweight(to_tsvector('english', coalesce(expert_name, '')), 'A') ||
                setweight(to_tsvector('english', coalesce(preview, '')), 'B') ||
                setweight(to_tsvector('english', coalesce(designation, '')), 'C') ||
                setweight(to_tsvector('english', coalesce(array_to_string(domains, ' '), '')), 'D') ||
                setweight(to_tsvector('english', coalesce(array_to_string(geographies, ' '), '')), 'D')
        $$ LANGUAGE sql IMMUTABLE;
        """
    )

    op.execute(
        """
        CREATE INDEX ix_transcripts_search_tsv ON transcripts
        USING gin (transcripts_search_vector(topic, expert_name, preview, designation, domains, geographies))
        """
    )

    op.execute("CREATE INDEX ix_transcripts_topic_trgm ON transcripts USING gin (topic gin_trgm_ops)")
    op.execute("CREATE INDEX ix_transcripts_expert_name_trgm ON transcripts USING gin (expert_name gin_trgm_ops)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_transcripts_expert_name_trgm")
    op.execute("DROP INDEX IF EXISTS ix_transcripts_topic_trgm")
    op.execute("DROP INDEX IF EXISTS ix_transcripts_search_tsv")
    op.execute("DROP FUNCTION IF EXISTS transcripts_search_vector(text, text, text, text, text[], text[])")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
