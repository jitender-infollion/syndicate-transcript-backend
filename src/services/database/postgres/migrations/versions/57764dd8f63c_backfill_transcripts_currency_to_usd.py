"""backfill transcripts currency to usd

Revision ID: 57764dd8f63c
Revises: b531b769575c
Create Date: 2026-08-19 00:00:00.000000

Existing rows inserted before b531b769575c carry whatever the old default
produced - 'INR' (DB-level server_default) or the literal string "USA"
(the ORM-level default, which was a typo for a currency code and took
precedence over the server_default on ORM inserts). Rewrites both to 'USD'
to match the new default. No downgrade path - the original values aren't
recoverable from the current data (nothing records which rows were 'INR'
vs "USA" vs an intentional non-default value), and none of these were valid
currency codes actual charges were made in.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '57764dd8f63c'
down_revision: Union[str, None] = 'b531b769575c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE transcripts SET currency = 'USD' WHERE currency IN ('INR', 'USA')")


def downgrade() -> None:
    pass
