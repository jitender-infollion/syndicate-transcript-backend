"""add coupons and coupon_redemptions tables

Revision ID: 8f0eb76ea1bc
Revises: 9682a1697e06
Create Date: 2026-08-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8f0eb76ea1bc'
down_revision: Union[str, None] = '9682a1697e06'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'coupons',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(), nullable=False),
        sa.Column('discount_type', sa.String(), nullable=False),
        sa.Column('discount_value', sa.Integer(), nullable=False),
        sa.Column('max_discount_amount', sa.Integer(), nullable=True),
        sa.Column('min_order_amount', sa.Integer(), server_default=sa.text('0'), nullable=True),
        sa.Column('usage_limit', sa.Integer(), nullable=True),
        sa.Column('usage_count', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('per_user_limit', sa.Integer(), server_default=sa.text('1'), nullable=True),
        sa.Column('is_stackable', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('valid_from', sa.DateTime(), nullable=True),
        sa.Column('valid_until', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
    )
    op.create_index(op.f('ix_coupons_id'), 'coupons', ['id'], unique=False)
    op.create_index(op.f('ix_coupons_code'), 'coupons', ['code'], unique=False)
    op.create_index(
        'ix_coupons_is_active_valid_from_valid_until', 'coupons', ['is_active', 'valid_from', 'valid_until'],
        unique=False,
    )

    op.create_table(
        'coupon_redemptions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('coupon_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('discount_applied', sa.Integer(), nullable=False),
        sa.Column('redeemed_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['coupon_id'], ['coupons.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('order_id'),
    )
    op.create_index(op.f('ix_coupon_redemptions_id'), 'coupon_redemptions', ['id'], unique=False)
    op.create_index(op.f('ix_coupon_redemptions_order_id'), 'coupon_redemptions', ['order_id'], unique=False)
    op.create_index(
        'ix_coupon_redemptions_coupon_id_user_id', 'coupon_redemptions', ['coupon_id', 'user_id'], unique=False
    )


def downgrade() -> None:
    op.drop_index('ix_coupon_redemptions_coupon_id_user_id', table_name='coupon_redemptions')
    op.drop_index(op.f('ix_coupon_redemptions_order_id'), table_name='coupon_redemptions')
    op.drop_index(op.f('ix_coupon_redemptions_id'), table_name='coupon_redemptions')
    op.drop_table('coupon_redemptions')

    op.drop_index('ix_coupons_is_active_valid_from_valid_until', table_name='coupons')
    op.drop_index(op.f('ix_coupons_code'), table_name='coupons')
    op.drop_index(op.f('ix_coupons_id'), table_name='coupons')
    op.drop_table('coupons')
