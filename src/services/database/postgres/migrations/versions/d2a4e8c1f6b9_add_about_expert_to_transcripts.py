"""add about_expert to transcripts

Revision ID: d2a4e8c1f6b9
Revises: c4f9a2e6b8d1
Create Date: 2026-09-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd2a4e8c1f6b9'
down_revision: Union[str, None] = 'c4f9a2e6b8d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('transcripts', sa.Column('about_expert', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('transcripts', 'about_expert')
