"""remove expert_name from search

Revision ID: fc4468e7a504
Revises: df3b7e404367
Create Date: 2026-08-19 00:00:00.000000

Drops expert_name from the transcript search document entirely (no full-text
weight, no trigram typo matching) - search now only covers topic/preview/
designation/domains/geographies. transcripts_search_vector's signature
changes (expert_name parameter removed), so the dependent GIN index has to
be dropped and rebuilt against the new function, and the now-unused
expert_name trigram index is dropped too.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'fc4468e7a504'
down_revision: Union[str, None] = 'df3b7e404367'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_transcripts_expert_name_trgm")
    op.execute("DROP INDEX ix_transcripts_search_tsv")
    op.execute("DROP FUNCTION transcripts_search_vector(text, text, text, text, text[], text[])")

    op.execute(
        """
        CREATE FUNCTION transcripts_search_vector(
            topic text, preview text, designation text,
            domains text[], geographies text[]
        ) RETURNS tsvector AS $$
            SELECT
                setweight(to_tsvector('english', coalesce(topic, '')), 'A') ||
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
        USING gin (transcripts_search_vector(topic, preview, designation, domains, geographies))
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX ix_transcripts_search_tsv")
    op.execute("DROP FUNCTION transcripts_search_vector(text, text, text, text[], text[])")

    op.execute(
        """
        CREATE FUNCTION transcripts_search_vector(
            topic text, expert_name text, preview text, designation text,
            domains text[], geographies text[]
        ) RETURNS tsvector AS $$
            SELECT
                setweight(to_tsvector('english', coalesce(topic, '')), 'A') ||
                setweight(to_tsvector('english', coalesce(preview, '')), 'B') ||
                setweight(to_tsvector('english', coalesce(designation, '')), 'C') ||
                setweight(to_tsvector('english', coalesce(expert_name, '')), 'D') ||
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
    op.execute("CREATE INDEX ix_transcripts_expert_name_trgm ON transcripts USING gin (expert_name gin_trgm_ops)")
