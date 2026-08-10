"""scope idempotency_key uniqueness to user_id

Revision ID: fb58a201c577
Revises: 267164a7746d
Create Date: 2026-08-06 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'fb58a201c577'
down_revision: Union[str, None] = '267164a7746d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Was a global UNIQUE index on idempotency_key alone - a collision across
    # two different users would crash the second user's checkout (see
    # orders_handler.create_order's IntegrityError recovery path, which
    # re-queries scoped to user_id + key and would find nothing).
    op.drop_index('ix_orders_idempotency_key', table_name='orders')
    op.create_index('ix_orders_idempotency_key', 'orders', ['idempotency_key'], unique=False)
    op.create_unique_constraint('uq_orders_user_idempotency_key', 'orders', ['user_id', 'idempotency_key'])


def downgrade() -> None:
    op.drop_constraint('uq_orders_user_idempotency_key', 'orders', type_='unique')
    op.drop_index('ix_orders_idempotency_key', table_name='orders')
    op.create_index('ix_orders_idempotency_key', 'orders', ['idempotency_key'], unique=True)
