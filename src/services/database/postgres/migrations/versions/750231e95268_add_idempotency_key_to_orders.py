"""add idempotency_key to orders

Revision ID: 750231e95268
Revises: e92d7449dac6
Create Date: 2026-08-05 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '750231e95268'
down_revision: Union[str, None] = 'e92d7449dac6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('orders', sa.Column('idempotency_key', sa.String(), nullable=True))
    op.create_index(op.f('ix_orders_idempotency_key'), 'orders', ['idempotency_key'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_orders_idempotency_key'), table_name='orders')
    op.drop_column('orders', 'idempotency_key')
