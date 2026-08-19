"""default transcripts currency to usd

Revision ID: b531b769575c
Revises: e5eb03d596db
Create Date: 2026-08-19 00:00:00.000000

transcripts.currency defaulted to 'INR' at the DB level while the ORM-level
default was the typo "USA" (not a currency code) - both inconsistent with
orders/payments, which default to PAYMENT_CURRENCY=USD (config.py). Switches
the column default to 'USD' to match.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b531b769575c'
down_revision: Union[str, None] = 'e5eb03d596db'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('transcripts', 'currency', server_default='USD')


def downgrade() -> None:
    op.alter_column('transcripts', 'currency', server_default='INR')
