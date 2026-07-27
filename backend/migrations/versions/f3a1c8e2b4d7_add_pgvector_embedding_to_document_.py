"""add pgvector embedding to document_chunks, replacing Qdrant

Revision ID: f3a1c8e2b4d7
Revises: dd97d6a9f1ae
Create Date: 2026-07-27 17:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = 'f3a1c8e2b4d7'
down_revision: Union[str, Sequence[str], None] = 'dd97d6a9f1ae'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Must match app.embeddings.embedder.EMBEDDING_DIMENSION /
# app.models.document._EMBEDDING_DIMENSION.
_EMBEDDING_DIMENSION = 384


def upgrade() -> None:
    """Upgrade schema."""
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    op.add_column(
        'document_chunks',
        sa.Column('embedding', Vector(_EMBEDDING_DIMENSION), nullable=True),
    )
    # HNSW (not IVFFlat): no training/"lists" tuning needed and the corpus
    # here (thousands of chunks, not millions) is well within HNSW's sweet
    # spot. vector_cosine_ops matches VectorRepository's cosine_distance()
    # query -- an index built for the wrong distance operator is silently
    # ignored by the planner, not an error, so this has to match exactly.
    op.execute(
        'CREATE INDEX ix_document_chunks_embedding_hnsw ON document_chunks '
        'USING hnsw (embedding vector_cosine_ops)'
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute('DROP INDEX IF EXISTS ix_document_chunks_embedding_hnsw')
    op.drop_column('document_chunks', 'embedding')
