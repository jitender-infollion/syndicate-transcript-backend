"""add orders and order_items tables

Revision ID: e92d7449dac6
Revises: 9e9d6ae7e372
Create Date: 2026-08-05 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e92d7449dac6'
down_revision: Union[str, None] = '9e9d6ae7e372'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('orders',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(), server_default='created', nullable=False),
    sa.Column('amount', sa.Integer(), nullable=False),
    sa.Column('currency', sa.String(), nullable=False),
    sa.Column('gateway', sa.String(), nullable=False),
    sa.Column('gateway_order_id', sa.String(), nullable=False),
    sa.Column('gateway_payment_id', sa.String(), nullable=True),
    sa.Column('last_webhook_event_id', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.Column('paid_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('gateway_order_id'),
    sa.UniqueConstraint('gateway_payment_id')
    )
    op.create_index(op.f('ix_orders_id'), 'orders', ['id'], unique=False)
    op.create_index(op.f('ix_orders_user_id'), 'orders', ['user_id'], unique=False)
    op.create_index(op.f('ix_orders_gateway_order_id'), 'orders', ['gateway_order_id'], unique=False)
    op.create_index(op.f('ix_orders_gateway_payment_id'), 'orders', ['gateway_payment_id'], unique=False)
    op.create_index('ix_orders_user_id_status', 'orders', ['user_id', 'status'], unique=False)

    op.create_table('order_items',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('order_id', sa.Integer(), nullable=False),
    sa.Column('transcript_id', sa.Integer(), nullable=False),
    sa.Column('price', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['transcript_id'], ['transcripts.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('order_id', 'transcript_id', name='uq_order_items_order_transcript')
    )
    op.create_index(op.f('ix_order_items_id'), 'order_items', ['id'], unique=False)

    # entitlements.order_item_id was FK-less until order_items existed - add the
    # real constraint now (see apis/models/entitlement/model.py).
    op.create_foreign_key(
        'fk_entitlements_order_item_id', 'entitlements', 'order_items', ['order_item_id'], ['id']
    )


def downgrade() -> None:
    op.drop_constraint('fk_entitlements_order_item_id', 'entitlements', type_='foreignkey')

    op.drop_index(op.f('ix_order_items_id'), table_name='order_items')
    op.drop_table('order_items')

    op.drop_index('ix_orders_user_id_status', table_name='orders')
    op.drop_index(op.f('ix_orders_gateway_payment_id'), table_name='orders')
    op.drop_index(op.f('ix_orders_gateway_order_id'), table_name='orders')
    op.drop_index(op.f('ix_orders_user_id'), table_name='orders')
    op.drop_index(op.f('ix_orders_id'), table_name='orders')
    op.drop_table('orders')
