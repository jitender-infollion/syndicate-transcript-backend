"""add support_messages and topic_requests tables

Revision ID: 267164a7746d
Revises: b954eef7a372
Create Date: 2026-08-06 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '267164a7746d'
down_revision: Union[str, None] = 'b954eef7a372'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('support_messages',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('email', sa.String(), nullable=False),
    sa.Column('message', sa.Text(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('ip_address', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_support_messages_id'), 'support_messages', ['id'], unique=False)

    op.create_table('topic_requests',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('topic', sa.String(), nullable=False),
    sa.Column('domain', sa.String(), nullable=False),
    sa.Column('email', sa.String(), nullable=True),
    sa.Column('remark', sa.Text(), nullable=True),
    sa.Column('suggested_expert_name', sa.String(), nullable=True),
    sa.Column('suggested_expert_linkedin', sa.String(), nullable=True),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('ip_address', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_topic_requests_id'), 'topic_requests', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_topic_requests_id'), table_name='topic_requests')
    op.drop_table('topic_requests')

    op.drop_index(op.f('ix_support_messages_id'), table_name='support_messages')
    op.drop_table('support_messages')
