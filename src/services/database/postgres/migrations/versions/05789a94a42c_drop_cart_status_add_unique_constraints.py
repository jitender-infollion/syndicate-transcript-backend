"""drop carts.status, enforce one cart per user/guest

Revision ID: 05789a94a42c
Revises: 515322798792
Create Date: 2026-08-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '05789a94a42c'
down_revision: Union[str, None] = '515322798792'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index('uq_carts_active_user', table_name='carts', postgresql_where=sa.text("status = 'active' AND user_id IS NOT NULL"))
    op.drop_index('uq_carts_active_guest', table_name='carts', postgresql_where=sa.text("status = 'active' AND guest_id IS NOT NULL"))
    op.drop_index('ix_carts_user_id_status', table_name='carts')
    op.drop_column('carts', 'status')

    op.create_unique_constraint('uq_carts_user_id', 'carts', ['user_id'])
    op.create_unique_constraint('uq_carts_guest_id', 'carts', ['guest_id'])


def downgrade() -> None:
    op.drop_constraint('uq_carts_guest_id', 'carts', type_='unique')
    op.drop_constraint('uq_carts_user_id', 'carts', type_='unique')

    op.add_column('carts', sa.Column('status', sa.String(), server_default='active', nullable=False))
    op.create_index('ix_carts_user_id_status', 'carts', ['user_id', 'status'], unique=False)
    op.create_index(
        'uq_carts_active_guest', 'carts', ['guest_id'], unique=True,
        postgresql_where=sa.text("status = 'active' AND guest_id IS NOT NULL"),
    )
    op.create_index(
        'uq_carts_active_user', 'carts', ['user_id'], unique=True,
        postgresql_where=sa.text("status = 'active' AND user_id IS NOT NULL"),
    )
