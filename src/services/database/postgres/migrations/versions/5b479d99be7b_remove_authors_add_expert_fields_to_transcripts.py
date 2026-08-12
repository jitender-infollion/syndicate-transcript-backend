"""remove authors table, add expert fields to transcripts

Revision ID: 5b479d99be7b
Revises: 8f3c3bd08dea
Create Date: 2026-08-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5b479d99be7b'
down_revision: Union[str, None] = '8f3c3bd08dea'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('transcripts', sa.Column('fk_expert', sa.BigInteger(), nullable=True))
    op.add_column('transcripts', sa.Column('expert_name', sa.String(), nullable=True))
    op.add_column('transcripts', sa.Column('designation', sa.String(), nullable=True))
    op.add_column('transcripts', sa.Column('years_of_experience', sa.Integer(), nullable=True))

    # Backfill from the author_id/authors data being retired, so existing rows satisfy the NOT NULL below.
    op.execute('UPDATE transcripts SET fk_expert = author_id')
    op.execute(
        "UPDATE transcripts SET expert_name = authors.name, designation = authors.designation "
        "FROM authors WHERE authors.id = transcripts.author_id"
    )
    op.alter_column('transcripts', 'fk_expert', nullable=False)
    op.create_index('ix_transcripts_fk_expert', 'transcripts', ['fk_expert'], unique=False)

    op.drop_index('ix_transcripts_author_id', table_name='transcripts')
    op.drop_constraint('transcripts_author_id_fkey', 'transcripts', type_='foreignkey')
    op.drop_column('transcripts', 'author_id')

    op.drop_index('ix_authors_id', table_name='authors')
    op.drop_table('authors')


def downgrade() -> None:
    op.create_table('authors',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=True),
        sa.Column('designation', sa.String(), nullable=True),
        sa.Column('experience', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_authors_id', 'authors', ['id'], unique=False)

    op.add_column('transcripts', sa.Column('author_id', sa.Integer(), nullable=False))
    op.create_foreign_key('transcripts_author_id_fkey', 'transcripts', 'authors', ['author_id'], ['id'])
    op.create_index('ix_transcripts_author_id', 'transcripts', ['author_id'], unique=False)

    op.drop_index('ix_transcripts_fk_expert', table_name='transcripts')
    op.drop_column('transcripts', 'years_of_experience')
    op.drop_column('transcripts', 'designation')
    op.drop_column('transcripts', 'expert_name')
    op.drop_column('transcripts', 'fk_expert')
