"""drop raw_response column from payments

Revision ID: a9dca1563692
Revises: a3f7c9b2d451
Create Date: 2026-08-08 23:56:35.968944

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a9dca1563692'
down_revision: Union[str, None] = 'a3f7c9b2d451'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column('payments', 'raw_response')


def downgrade() -> None:
    op.add_column('payments', sa.Column('raw_response', sa.JSON(), nullable=True))
