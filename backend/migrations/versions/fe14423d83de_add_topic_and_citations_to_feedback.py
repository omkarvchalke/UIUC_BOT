"""add topic and citations to feedback

Revision ID: fe14423d83de
Revises: f3a1c8e2b4d7
Create Date: 2026-07-29 02:01:34.303032

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'fe14423d83de'
down_revision: Union[str, Sequence[str], None] = 'f3a1c8e2b4d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Note: autogenerate also proposed dropping the checkpoint_* tables and
    # the ix_document_chunks_embedding_hnsw index -- both known false
    # positives already documented in dd97d6a9f1ae and f3a1c8e2b4d7
    # respectively (unmanaged langgraph tables / a raw-SQL-created index
    # outside Base.metadata). Removed from this migration by hand.
    op.add_column(
        'feedback',
        sa.Column(
            'topic',
            sa.Enum(
                'admissions', 'registration', 'orientation', 'housing', 'dining',
                'financial_aid', 'scholarships', 'student_employment',
                'international_student_services', 'visa', 'cpt', 'opt',
                'technology_services', 'libraries', 'transportation',
                'health_insurance', 'campus_recreation', 'student_organizations',
                'academic_calendar', 'course_registration', 'campus_safety',
                'accessibility', 'career_services', 'academic_advising',
                name='topic', native_enum=False, length=64,
            ),
            nullable=True,
        ),
    )
    op.add_column(
        'feedback',
        sa.Column('citations', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('feedback', 'citations')
    op.drop_column('feedback', 'topic')
