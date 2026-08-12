"""rename support_messages to support_tickets, encrypt emails on both inquiry tables

Revision ID: 869cd8f5eac6
Revises: 8f0eb76ea1bc
Create Date: 2026-08-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from services.crypto.email_crypto import encrypt_email, hash_email


# revision identifiers, used by Alembic.
revision: str = '869cd8f5eac6'
down_revision: Union[str, None] = '8f0eb76ea1bc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.rename_table('support_messages', 'support_tickets')
    op.execute('ALTER INDEX ix_support_messages_id RENAME TO ix_support_tickets_id')
    op.execute('ALTER TABLE support_tickets RENAME CONSTRAINT support_messages_pkey TO support_tickets_pkey')
    op.execute(
        'ALTER TABLE support_tickets RENAME CONSTRAINT support_messages_user_id_fkey '
        'TO support_tickets_user_id_fkey'
    )

    op.alter_column('support_tickets', 'email', new_column_name='email_encrypted')
    op.add_column('support_tickets', sa.Column('email_hash', sa.String(), nullable=True))
    op.create_index('ix_support_tickets_status', 'support_tickets', ['status'], unique=False)
    op.create_index('ix_support_tickets_user_id', 'support_tickets', ['user_id'], unique=False)
    op.create_index('ix_support_tickets_email_hash', 'support_tickets', ['email_hash'], unique=False)

    op.add_column('topic_requests', sa.Column('name', sa.String(), nullable=True))
    op.alter_column('topic_requests', 'email', new_column_name='email_encrypted')
    op.add_column('topic_requests', sa.Column('email_hash', sa.String(), nullable=True))
    op.create_index('ix_topic_requests_status', 'topic_requests', ['status'], unique=False)
    op.create_index('ix_topic_requests_user_id', 'topic_requests', ['user_id'], unique=False)
    op.create_index('ix_topic_requests_email_hash', 'topic_requests', ['email_hash'], unique=False)

    # The column previously held plaintext emails - encrypt/hash existing rows in place
    # now that the app-level crypto helpers exist, before enforcing NOT NULL.
    bind = op.get_bind()
    for table in ('support_tickets', 'topic_requests'):
        rows = bind.execute(sa.text(f'SELECT id, email_encrypted FROM {table}')).fetchall()
        for row_id, plaintext in rows:
            bind.execute(
                sa.text(f'UPDATE {table} SET email_encrypted = :enc, email_hash = :hash WHERE id = :id'),
                {"enc": encrypt_email(plaintext), "hash": hash_email(plaintext), "id": row_id},
            )
    op.alter_column('support_tickets', 'email_hash', nullable=False)


def downgrade() -> None:
    op.drop_index('ix_topic_requests_email_hash', table_name='topic_requests')
    op.drop_index('ix_topic_requests_user_id', table_name='topic_requests')
    op.drop_index('ix_topic_requests_status', table_name='topic_requests')
    op.drop_column('topic_requests', 'email_hash')
    op.alter_column('topic_requests', 'email_encrypted', new_column_name='email')
    op.drop_column('topic_requests', 'name')

    op.drop_index('ix_support_tickets_email_hash', table_name='support_tickets')
    op.drop_index('ix_support_tickets_user_id', table_name='support_tickets')
    op.drop_index('ix_support_tickets_status', table_name='support_tickets')
    op.drop_column('support_tickets', 'email_hash')
    op.alter_column('support_tickets', 'email_encrypted', new_column_name='email')

    op.execute(
        'ALTER TABLE support_tickets RENAME CONSTRAINT support_tickets_user_id_fkey '
        'TO support_messages_user_id_fkey'
    )
    op.execute('ALTER TABLE support_tickets RENAME CONSTRAINT support_tickets_pkey TO support_messages_pkey')
    op.execute('ALTER INDEX ix_support_tickets_id RENAME TO ix_support_messages_id')
    op.rename_table('support_tickets', 'support_messages')
