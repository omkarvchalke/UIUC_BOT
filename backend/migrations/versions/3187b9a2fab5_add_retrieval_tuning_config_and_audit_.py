"""add retrieval tuning config and audit tables

Revision ID: 3187b9a2fab5
Revises: fe14423d83de
Create Date: 2026-07-29 02:03:19.947407

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '3187b9a2fab5'
down_revision: Union[str, Sequence[str], None] = 'fe14423d83de'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Note: autogenerate also proposed dropping the checkpoint_* tables and
    # the ix_document_chunks_embedding_hnsw index -- both known false
    # positives, same as fe14423d83de. Removed from this migration by hand.
    op.create_table('retrieval_tuning_audit_log',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('parameter', sa.Text(), nullable=False),
    sa.Column('old_value', sa.Float(), nullable=False),
    sa.Column('new_value', sa.Float(), nullable=False),
    sa.Column('applied', sa.Boolean(), nullable=False),
    sa.Column('reason', sa.Text(), nullable=False),
    sa.Column('sample_size', sa.Integer(), nullable=False),
    sa.Column('flag_rate', sa.Float(), nullable=False),
    sa.Column('golden_set_before', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('golden_set_after', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('retrieval_tuning_config',
    sa.Column('key', sa.Text(), nullable=False),
    sa.Column('value', sa.Float(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('key')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('retrieval_tuning_config')
    op.drop_table('retrieval_tuning_audit_log')
