"""widen id and foreign-key columns to bigint

Revision ID: 515322798792
Revises: 869cd8f5eac6
Create Date: 2026-08-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '515322798792'
down_revision: Union[str, None] = '869cd8f5eac6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (table, column) pairs - every primary key and foreign key column, widened
# from int4 to int8. Postgres allows FK constraints across int4/int8 (there's
# a built-in cross-type equality operator), so these can run in any order
# without dropping constraints, and indexes are rebuilt automatically.
_COLUMNS = [
    ('users', 'id'),
    ('sessions', 'id'),
    ('sessions', 'user_id'),
    ('transcripts', 'id'),
    ('carts', 'id'),
    ('carts', 'user_id'),
    ('cart_items', 'id'),
    ('cart_items', 'cart_id'),
    ('cart_items', 'transcript_id'),
    ('orders', 'id'),
    ('orders', 'user_id'),
    ('order_items', 'id'),
    ('order_items', 'order_id'),
    ('order_items', 'user_id'),
    ('order_items', 'transcript_id'),
    ('payments', 'id'),
    ('payments', 'order_id'),
    ('receipts', 'id'),
    ('receipts', 'order_id'),
    ('coupons', 'id'),
    ('coupon_redemptions', 'id'),
    ('coupon_redemptions', 'coupon_id'),
    ('coupon_redemptions', 'user_id'),
    ('coupon_redemptions', 'order_id'),
    ('topic_requests', 'id'),
    ('topic_requests', 'user_id'),
    ('support_tickets', 'id'),
    ('support_tickets', 'user_id'),
]


def upgrade() -> None:
    for table, column in _COLUMNS:
        op.alter_column(table, column, type_=sa.BigInteger(), existing_type=sa.Integer())


def downgrade() -> None:
    for table, column in reversed(_COLUMNS):
        op.alter_column(table, column, type_=sa.Integer(), existing_type=sa.BigInteger())
