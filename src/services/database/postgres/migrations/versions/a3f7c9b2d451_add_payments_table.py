"""add payments table, move gateway fields off orders

Revision ID: a3f7c9b2d451
Revises: fb58a201c577
Create Date: 2026-08-06 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3f7c9b2d451'
down_revision: Union[str, None] = 'fb58a201c577'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('payments',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('order_id', sa.Integer(), nullable=False),
    sa.Column('provider', sa.String(), nullable=False),
    sa.Column('provider_order_id', sa.String(), nullable=False),
    sa.Column('provider_payment_id', sa.String(), nullable=True),
    sa.Column('provider_signature', sa.String(), nullable=True),
    sa.Column('amount', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(), server_default='pending', nullable=False),
    sa.Column('webhook_event_id', sa.String(), nullable=True),
    sa.Column('raw_response', sa.JSON(), nullable=True),
    sa.Column('paid_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('provider', 'provider_order_id', name='uq_payments_provider_order_id'),
    sa.UniqueConstraint('provider', 'provider_payment_id', name='uq_payments_provider_payment_id'),
    sa.UniqueConstraint('webhook_event_id')
    )
    op.create_index(op.f('ix_payments_id'), 'payments', ['id'], unique=False)
    op.create_index('ix_payments_order_id', 'payments', ['order_id'], unique=False)

    # Backfill: one payment row per existing order, carrying over what used to
    # live directly on orders. orders.status ('created'/'paid'/'failed') and
    # payments.status ('pending'/'paid'/'failed'/'refunded') are different
    # vocabularies - 'created' has no direct equivalent, map it to 'pending'.
    op.execute(
        """
        INSERT INTO payments (order_id, provider, provider_order_id, provider_payment_id, amount, status, paid_at, created_at)
        SELECT id, gateway, gateway_order_id, gateway_payment_id, amount,
               CASE status WHEN 'created' THEN 'pending' ELSE status END,
               paid_at, created_at
        FROM orders
        """
    )

    op.drop_index(op.f('ix_orders_gateway_payment_id'), table_name='orders')
    op.drop_index(op.f('ix_orders_gateway_order_id'), table_name='orders')
    op.drop_constraint('orders_gateway_payment_id_key', 'orders', type_='unique')
    op.drop_constraint('orders_gateway_order_id_key', 'orders', type_='unique')
    op.drop_column('orders', 'last_webhook_event_id')
    op.drop_column('orders', 'gateway_payment_id')
    op.drop_column('orders', 'gateway_order_id')
    op.drop_column('orders', 'gateway')


def downgrade() -> None:
    op.add_column('orders', sa.Column('gateway', sa.String(), nullable=True))
    op.add_column('orders', sa.Column('gateway_order_id', sa.String(), nullable=True))
    op.add_column('orders', sa.Column('gateway_payment_id', sa.String(), nullable=True))
    op.add_column('orders', sa.Column('last_webhook_event_id', sa.String(), nullable=True))

    op.execute(
        """
        UPDATE orders o
        SET gateway = p.provider,
            gateway_order_id = p.provider_order_id,
            gateway_payment_id = p.provider_payment_id,
            last_webhook_event_id = p.webhook_event_id
        FROM payments p
        WHERE p.order_id = o.id
        """
    )

    op.alter_column('orders', 'gateway', nullable=False)
    op.alter_column('orders', 'gateway_order_id', nullable=False)
    op.create_unique_constraint('orders_gateway_order_id_key', 'orders', ['gateway_order_id'])
    op.create_unique_constraint('orders_gateway_payment_id_key', 'orders', ['gateway_payment_id'])
    op.create_index(op.f('ix_orders_gateway_order_id'), 'orders', ['gateway_order_id'], unique=False)
    op.create_index(op.f('ix_orders_gateway_payment_id'), 'orders', ['gateway_payment_id'], unique=False)

    op.drop_index('ix_payments_order_id', table_name='payments')
    op.drop_index(op.f('ix_payments_id'), table_name='payments')
    op.drop_table('payments')
