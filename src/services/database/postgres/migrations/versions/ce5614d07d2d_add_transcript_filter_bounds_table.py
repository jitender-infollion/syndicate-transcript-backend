"""add transcript_filter_bounds table

Revision ID: ce5614d07d2d
Revises: 3970e3b6a3d1
Create Date: 2026-08-17 10:00:00.000000

Single-row table caching min/max price and min/max published_at across active
transcripts, so the frontend can size filter sliders/date-range without
scanning the whole transcripts table on every page load. Kept in sync by a
DB trigger rather than application code, so it can't drift out of date
regardless of which code path writes to transcripts.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'ce5614d07d2d'
down_revision: Union[str, None] = '3970e3b6a3d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'transcript_filter_bounds',
        sa.Column('id', sa.SmallInteger(), nullable=False),
        sa.Column('min_price', sa.BigInteger(), nullable=True),
        sa.Column('max_price', sa.BigInteger(), nullable=True),
        sa.Column('min_published_at', sa.DateTime(), nullable=True),
        sa.Column('max_published_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('id = 1', name='ck_transcript_filter_bounds_singleton'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.execute(
        """
        CREATE FUNCTION refresh_transcript_filter_bounds() RETURNS trigger AS $$
        BEGIN
            INSERT INTO transcript_filter_bounds
                (id, min_price, max_price, min_published_at, max_published_at, updated_at)
            SELECT 1, MIN(price), MAX(price), MIN(published_at), MAX(published_at), now()
            FROM transcripts
            WHERE is_active = true
            ON CONFLICT (id) DO UPDATE SET
                min_price = EXCLUDED.min_price,
                max_price = EXCLUDED.max_price,
                min_published_at = EXCLUDED.min_published_at,
                max_published_at = EXCLUDED.max_published_at,
                updated_at = EXCLUDED.updated_at;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute(
        """
        CREATE TRIGGER trg_refresh_transcript_filter_bounds
        AFTER INSERT OR DELETE OR UPDATE OF price, is_active, published_at
        ON transcripts
        FOR EACH STATEMENT
        EXECUTE FUNCTION refresh_transcript_filter_bounds();
        """
    )

    # Backfill from whatever is already in transcripts, so the row isn't empty
    # until the next write.
    op.execute(
        """
        INSERT INTO transcript_filter_bounds
            (id, min_price, max_price, min_published_at, max_published_at, updated_at)
        SELECT 1, MIN(price), MAX(price), MIN(published_at), MAX(published_at), now()
        FROM transcripts
        WHERE is_active = true
        """
    )


def downgrade() -> None:
    op.execute('DROP TRIGGER IF EXISTS trg_refresh_transcript_filter_bounds ON transcripts')
    op.execute('DROP FUNCTION IF EXISTS refresh_transcript_filter_bounds()')
    op.drop_table('transcript_filter_bounds')
