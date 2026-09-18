"""require preview, domains, key_insights on transcripts

Revision ID: a7f3b0e2c9d4
Revises: d2a4e8c1f6b9
Create Date: 2026-09-18

Backfills any existing NULLs before adding the NOT NULL constraints, since
older rows (seeded before these were enforced at the API layer) may still
have them unset. preview backfills to '' and the two arrays to '{}' - empty
is still a valid value for all three, only NULL is being ruled out.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a7f3b0e2c9d4'
down_revision: Union[str, None] = 'd2a4e8c1f6b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE transcripts SET preview = '' WHERE preview IS NULL")
    op.execute("UPDATE transcripts SET domains = '{}' WHERE domains IS NULL")
    op.execute("UPDATE transcripts SET key_insights = '{}' WHERE key_insights IS NULL")

    op.alter_column('transcripts', 'preview', nullable=False)
    op.alter_column('transcripts', 'domains', nullable=False)
    op.alter_column('transcripts', 'key_insights', nullable=False)


def downgrade() -> None:
    op.alter_column('transcripts', 'preview', nullable=True)
    op.alter_column('transcripts', 'domains', nullable=True)
    op.alter_column('transcripts', 'key_insights', nullable=True)
