"""add feedback table

Revision ID: 5f58f96b77b0
Revises: 8033c30d4184
Create Date: 2026-07-15 12:05:37.564419

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '5f58f96b77b0'
down_revision: Union[str, Sequence[str], None] = '8033c30d4184'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Note: autogenerate also proposed dropping the checkpoints /
    # checkpoint_blobs / checkpoint_writes / checkpoint_migrations tables --
    # those are created at runtime by langgraph's AsyncPostgresSaver.setup()
    # (app/graph/checkpointer.py), not part of Base.metadata, so alembic's
    # diff sees them as "unmanaged" and wants them gone. Removed from this
    # migration by hand; dropping them would wipe all conversation history.
    op.create_table('feedback',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('session_id', sa.Uuid(), nullable=False),
    sa.Column('message_id', sa.Text(), nullable=False),
    sa.Column('question', sa.Text(), nullable=False),
    sa.Column('answer', sa.Text(), nullable=False),
    sa.Column('rating', sa.Enum('helpful', 'not_helpful', name='feedback_rating'), nullable=False),
    sa.Column('comment', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['session_id'], ['conversation_sessions.id'], ),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('feedback')
    sa.Enum(name='feedback_rating').drop(op.get_bind(), checkfirst=False)
