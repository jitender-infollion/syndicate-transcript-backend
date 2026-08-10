"""add status column to support_messages and topic_requests

Revision ID: 8f3c3bd08dea
Revises: 094efbdeec17
Create Date: 2026-08-09 00:21:46.037231

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8f3c3bd08dea'
down_revision: Union[str, None] = '094efbdeec17'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'support_messages',
        sa.Column('status', sa.String(), nullable=False, server_default='open'),
    )
    op.add_column(
        'topic_requests',
        sa.Column('status', sa.String(), nullable=False, server_default='open'),
    )


def downgrade() -> None:
    op.drop_column('topic_requests', 'status')
    op.drop_column('support_messages', 'status')
