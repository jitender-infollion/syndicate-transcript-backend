"""retire entitlements table, add access fields to order_items

Revision ID: 76aa05bc0fe6
Revises: 5b479d99be7b
Create Date: 2026-08-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '76aa05bc0fe6'
down_revision: Union[str, None] = '5b479d99be7b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('order_items', sa.Column('user_id', sa.Integer(), nullable=False))
    op.add_column('order_items', sa.Column('currency', sa.String(), nullable=False))
    op.add_column(
        'order_items',
        sa.Column('access_permission', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    )
    op.create_foreign_key('order_items_user_id_fkey', 'order_items', 'users', ['user_id'], ['id'])
    op.create_index('ix_order_items_user_id', 'order_items', ['user_id'], unique=False)
    op.create_index('ix_order_items_transcript_id', 'order_items', ['transcript_id'], unique=False)
    op.create_index(
        'ix_order_items_user_id_transcript_id', 'order_items', ['user_id', 'transcript_id'], unique=False
    )

    op.drop_index('ix_entitlements_user_id_status', table_name='entitlements')
    op.drop_index('ix_entitlements_order_item_id', table_name='entitlements')
    op.drop_index(op.f('ix_entitlements_id'), table_name='entitlements')
    op.drop_table('entitlements')


def downgrade() -> None:
    op.create_table('entitlements',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('transcript_id', sa.Integer(), nullable=False),
        sa.Column('order_item_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(), server_default='active', nullable=False),
        sa.Column('source', sa.String(), server_default='purchase', nullable=False),
        sa.Column('granted_at', sa.DateTime(), nullable=False),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['transcript_id'], ['transcripts.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['order_item_id'], ['order_items.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'transcript_id', name='uq_entitlements_user_transcript'),
    )
    op.create_index(op.f('ix_entitlements_id'), 'entitlements', ['id'], unique=False)
    op.create_index('ix_entitlements_order_item_id', 'entitlements', ['order_item_id'], unique=False)
    op.create_index('ix_entitlements_user_id_status', 'entitlements', ['user_id', 'status'], unique=False)

    op.drop_index('ix_order_items_user_id_transcript_id', table_name='order_items')
    op.drop_index('ix_order_items_transcript_id', table_name='order_items')
    op.drop_index('ix_order_items_user_id', table_name='order_items')
    op.drop_constraint('order_items_user_id_fkey', 'order_items', type_='foreignkey')
    op.drop_column('order_items', 'access_permission')
    op.drop_column('order_items', 'currency')
    op.drop_column('order_items', 'user_id')
