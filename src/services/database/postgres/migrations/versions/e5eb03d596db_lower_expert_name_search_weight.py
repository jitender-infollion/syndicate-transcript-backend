"""lower expert_name search weight

Revision ID: e5eb03d596db
Revises: 636c03a87feb
Create Date: 2026-08-19 00:00:00.000000

expert_name moves from weight 'A' (tied with topic) down to 'D' (tied with
domains/geographies, the lowest tier) - a name match should surface a
result but not outrank a real topic/preview match. transcripts_search_vector
is CREATE OR REPLACE'd in place (same signature, callers in
transcripts_helper.py are untouched) and the dependent GIN index is REINDEXed
- Postgres has no way to detect that a function backing an expression index
changed, so existing index entries would otherwise keep scoring by the old
weights until the next write to each row.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e5eb03d596db'
down_revision: Union[str, None] = '636c03a87feb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION transcripts_search_vector(
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
    op.execute("REINDEX INDEX ix_transcripts_search_tsv")


def downgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION transcripts_search_vector(
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
    op.execute("REINDEX INDEX ix_transcripts_search_tsv")
