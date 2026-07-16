"""add audience document_type keywords last_crawled_at subtopic document_versions

Revision ID: 5242feccd56c
Revises: 5f58f96b77b0
Create Date: 2026-07-16 00:19:54.147895

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '5242feccd56c'
down_revision: Union[str, Sequence[str], None] = '5f58f96b77b0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Note: the checkpoint_* tables autogenerate also detected are owned and
    # managed by LangGraph's AsyncPostgresSaver.setup() (app/graph/
    # checkpointer.py), not SQLAlchemy's Base.metadata -- alembic's
    # autogenerate diff doesn't know about them and proposes dropping them
    # on every future autogenerate run. Deliberately excluded here and in
    # every migration going forward; see that module's docstring.
    op.create_table(
        "document_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("captured_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_document_versions_document_id"),
        "document_versions",
        ["document_id"],
        unique=False,
    )
    op.add_column("document_chunks", sa.Column("subtopic", sa.String(length=255), nullable=True))
    # server_default='{}': audience/keywords are NOT NULL array columns
    # (Document.audience/.keywords are typed list[...], never Optional) --
    # without a server-side default, ALTER TABLE ADD COLUMN ... NOT NULL
    # fails outright against the ~1000+ existing rows. document_type stays
    # nullable (see the model's own comment: backfilled by
    # scripts/backfill_document_metadata.py, not this migration).
    op.add_column(
        "documents",
        sa.Column(
            "audience",
            sa.ARRAY(
                sa.Enum(
                    "prospective_student",
                    "current_student",
                    "faculty_staff",
                    "alumni",
                    "parent_family",
                    "general_public",
                    name="audience",
                    native_enum=False,
                    length=32,
                )
            ),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
    )
    op.add_column(
        "documents",
        sa.Column(
            "document_type",
            sa.Enum(
                "policy",
                "form",
                "faq",
                "deadline_reference",
                "news_announcement",
                "program_description",
                "how_to_guide",
                "contact_info",
                name="documenttype",
                native_enum=False,
                length=32,
            ),
            nullable=True,
        ),
    )
    op.add_column(
        "documents",
        sa.Column(
            "keywords", sa.ARRAY(sa.String(length=100)), server_default=sa.text("'{}'"), nullable=False
        ),
    )
    op.add_column("documents", sa.Column("last_crawled_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("documents", "last_crawled_at")
    op.drop_column("documents", "keywords")
    op.drop_column("documents", "document_type")
    op.drop_column("documents", "audience")
    op.drop_column("document_chunks", "subtopic")
    op.drop_index(op.f("ix_document_versions_document_id"), table_name="document_versions")
    op.drop_table("document_versions")
