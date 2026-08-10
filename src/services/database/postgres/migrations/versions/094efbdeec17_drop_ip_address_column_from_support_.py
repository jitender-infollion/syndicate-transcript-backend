"""drop ip_address column from support_messages and topic_requests

Revision ID: 094efbdeec17
Revises: a9dca1563692
Create Date: 2026-08-09 00:19:33.105726

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '094efbdeec17'
down_revision: Union[str, None] = 'a9dca1563692'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column('support_messages', 'ip_address')
    op.drop_column('topic_requests', 'ip_address')


def downgrade() -> None:
    op.add_column('support_messages', sa.Column('ip_address', sa.String(), nullable=True))
    op.add_column('topic_requests', sa.Column('ip_address', sa.String(), nullable=True))
