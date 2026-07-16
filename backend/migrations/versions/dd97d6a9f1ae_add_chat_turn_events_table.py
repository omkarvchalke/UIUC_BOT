"""add chat_turn_events table

Revision ID: dd97d6a9f1ae
Revises: 5242feccd56c
Create Date: 2026-07-16 05:30:51.789217

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "dd97d6a9f1ae"
down_revision: Union[str, Sequence[str], None] = "5242feccd56c"
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
    op.create_table(
        "chat_turn_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column(
            "intent", sa.Enum("greeting", "question", name="chat_turn_intent"), nullable=False
        ),
        sa.Column(
            "topic",
            sa.Enum(
                "admissions",
                "registration",
                "orientation",
                "housing",
                "dining",
                "financial_aid",
                "scholarships",
                "student_employment",
                "international_student_services",
                "visa",
                "cpt",
                "opt",
                "technology_services",
                "libraries",
                "transportation",
                "health_insurance",
                "campus_recreation",
                "student_organizations",
                "academic_calendar",
                "course_registration",
                "campus_safety",
                "accessibility",
                name="topic",
                native_enum=False,
                length=64,
            ),
            nullable=True,
        ),
        sa.Column("needs_clarification", sa.Boolean(), nullable=False),
        sa.Column("grounded", sa.Boolean(), nullable=True),
        sa.Column("citation_count", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["conversation_sessions.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("chat_turn_events")
    sa.Enum(name="chat_turn_intent").drop(op.get_bind(), checkfirst=False)
