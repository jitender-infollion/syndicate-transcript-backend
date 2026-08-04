"""convert transcripts domain and geography to arrays

Revision ID: 74fadc856197
Revises: 8d658e484901
Create Date: 2026-08-03 00:38:27.123710

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY

# revision identifiers, used by Alembic.
revision: str = '74fadc856197'
down_revision: Union[str, None] = '8d658e484901'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Autogenerate doesn't detect scalar->ARRAY type changes, so this is
    # hand-written. No backfill path from a single scalar value to a
    # meaningful array of several - truncate (all dummy seed data) rather
    # than wrap each value into a single-element array.
    op.execute("TRUNCATE TABLE transcripts RESTART IDENTITY CASCADE")

    op.drop_index("ix_transcripts_domain", table_name="transcripts")
    op.drop_index("ix_transcripts_geography", table_name="transcripts")

    op.drop_column("transcripts", "domain")
    op.drop_column("transcripts", "geography")
    op.add_column("transcripts", sa.Column("domain", ARRAY(sa.String()), nullable=True))
    op.add_column("transcripts", sa.Column("geography", ARRAY(sa.String()), nullable=True))

    op.create_index("ix_transcripts_domain", "transcripts", ["domain"], postgresql_using="gin")
    op.create_index("ix_transcripts_geography", "transcripts", ["geography"], postgresql_using="gin")


def downgrade() -> None:
    op.drop_index("ix_transcripts_domain", table_name="transcripts")
    op.drop_index("ix_transcripts_geography", table_name="transcripts")

    op.drop_column("transcripts", "domain")
    op.drop_column("transcripts", "geography")
    op.add_column("transcripts", sa.Column("domain", sa.String(), nullable=True))
    op.add_column("transcripts", sa.Column("geography", sa.String(), nullable=True))

    op.create_index("ix_transcripts_domain", "transcripts", ["domain"])
    op.create_index("ix_transcripts_geography", "transcripts", ["geography"])
