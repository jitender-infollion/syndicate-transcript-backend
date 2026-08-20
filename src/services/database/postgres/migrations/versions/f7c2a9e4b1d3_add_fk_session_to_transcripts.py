"""add fk_session to transcripts (idempotency key for Infollion publish upserts)

Revision ID: f7c2a9e4b1d3
Revises: ce5614d07d2d
Create Date: 2026-08-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f7c2a9e4b1d3'
down_revision: Union[str, None] = 'fc4468e7a504'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # fk_session = the Infollion syndicate_sessions.id. It is the idempotency key the
    # publish endpoint upserts on (INSERT ... ON CONFLICT (fk_session) DO UPDATE).
    # Nullable so any pre-existing rows (which predate this integration) stay valid;
    # UNIQUE so a re-publish updates the same row instead of inserting a duplicate.
    op.add_column('transcripts', sa.Column('fk_session', sa.BigInteger(), nullable=True))
    op.create_unique_constraint('uq_transcripts_fk_session', 'transcripts', ['fk_session'])


def downgrade() -> None:
    op.drop_constraint('uq_transcripts_fk_session', 'transcripts', type_='unique')
    op.drop_column('transcripts', 'fk_session')
