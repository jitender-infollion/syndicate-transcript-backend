"""convert transcripts.final_transcript to jsonb

Revision ID: e3681963f464
Revises: 05789a94a42c
Create Date: 2026-08-12 12:18:11.319014

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e3681963f464'
down_revision: Union[str, None] = '05789a94a42c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        'ALTER TABLE transcripts ALTER COLUMN final_transcript TYPE JSONB USING final_transcript::jsonb'
    )


def downgrade() -> None:
    op.execute(
        'ALTER TABLE transcripts ALTER COLUMN final_transcript TYPE JSON USING final_transcript::json'
    )
