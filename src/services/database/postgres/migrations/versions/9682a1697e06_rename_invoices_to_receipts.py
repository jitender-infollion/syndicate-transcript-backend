"""rename invoices to receipts, drop user_id, rename pdf_storage_key to pdf_url

Revision ID: 9682a1697e06
Revises: 76aa05bc0fe6
Create Date: 2026-08-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9682a1697e06'
down_revision: Union[str, None] = '76aa05bc0fe6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.rename_table('invoices', 'receipts')

    op.execute('ALTER INDEX ix_invoices_id RENAME TO ix_receipts_id')
    op.execute('ALTER INDEX ix_invoices_order_id RENAME TO ix_receipts_order_id')
    op.execute('ALTER INDEX ix_invoices_invoice_number RENAME TO ix_receipts_invoice_number')
    op.execute('ALTER TABLE receipts RENAME CONSTRAINT invoices_pkey TO receipts_pkey')
    op.execute('ALTER TABLE receipts RENAME CONSTRAINT invoices_order_id_key TO receipts_order_id_key')
    op.execute(
        'ALTER TABLE receipts RENAME CONSTRAINT invoices_invoice_number_key TO receipts_invoice_number_key'
    )
    op.execute('ALTER TABLE receipts RENAME CONSTRAINT invoices_order_id_fkey TO receipts_order_id_fkey')

    op.drop_index('ix_invoices_user_id', table_name='receipts')
    op.drop_constraint('invoices_user_id_fkey', 'receipts', type_='foreignkey')
    op.drop_column('receipts', 'user_id')

    op.alter_column('receipts', 'pdf_storage_key', new_column_name='pdf_url')


def downgrade() -> None:
    op.alter_column('receipts', 'pdf_url', new_column_name='pdf_storage_key')

    op.add_column('receipts', sa.Column('user_id', sa.Integer(), nullable=False))
    op.create_foreign_key('invoices_user_id_fkey', 'receipts', 'users', ['user_id'], ['id'])
    op.create_index('ix_invoices_user_id', 'receipts', ['user_id'], unique=False)

    op.execute('ALTER TABLE receipts RENAME CONSTRAINT receipts_order_id_fkey TO invoices_order_id_fkey')
    op.execute(
        'ALTER TABLE receipts RENAME CONSTRAINT receipts_invoice_number_key TO invoices_invoice_number_key'
    )
    op.execute('ALTER TABLE receipts RENAME CONSTRAINT receipts_order_id_key TO invoices_order_id_key')
    op.execute('ALTER TABLE receipts RENAME CONSTRAINT receipts_pkey TO invoices_pkey')
    op.execute('ALTER INDEX ix_receipts_invoice_number RENAME TO ix_invoices_invoice_number')
    op.execute('ALTER INDEX ix_receipts_order_id RENAME TO ix_invoices_order_id')
    op.execute('ALTER INDEX ix_receipts_id RENAME TO ix_invoices_id')

    op.rename_table('receipts', 'invoices')
