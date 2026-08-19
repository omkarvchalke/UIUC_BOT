"""Source Manifest V2 schema + topic taxonomy migration

Adds the Source Manifest V2 metadata columns to documents/document_chunks,
and remaps every existing Document.topic value from the previous 24-topic
taxonomy to the new 21-topic one (see app/models/document.py's Topic
docstring and backend/scripts/data/source_manifest_v2.md).

The topic remap here only handles the UNAMBIGUOUS 1:1 old-topic ->
new-topic renames via SQL. The one genuinely ambiguous old topic,
course_registration (split by Source Manifest V2 between ACADEMICS and
CAMPUS_SERVICES_FACILITIES depending on each page's actual content, not
determinable from the topic value alone), is given a defensible temporary
default (campus_services_facilities, since most of that old bucket was
catalog.illinois.edu subject-listing pages) and flagged index_status='review'
so scripts/remap_topics_v2.py's classifier-driven pass finds and correctly
reclassifies exactly those rows on its next run -- never left silently
mislabeled.

Revision ID: bcd06e256c7d
Revises: 3187b9a2fab5
Create Date: 2026-08-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bcd06e256c7d'
down_revision: Union[str, Sequence[str], None] = '3187b9a2fab5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (old_topic_value, new_topic_value) for every unambiguous 1:1 rename. Excludes
# course_registration (handled separately, see module docstring) and the topics that keep an
# identical value across both taxonomies (admissions, housing, dining, technology_services,
# libraries, campus_recreation, campus_safety, academic_advising -- nothing to update for those).
_TOPIC_RENAMES = (
    ("registration", "registration_records"),
    ("orientation", "orientation_new_students"),
    ("financial_aid", "financial_aid_scholarships"),
    ("scholarships", "financial_aid_scholarships"),
    ("student_employment", "career_employment"),
    ("career_services", "career_employment"),
    ("international_student_services", "international_students_immigration"),
    ("visa", "international_students_immigration"),
    ("cpt", "international_students_immigration"),
    ("opt", "international_students_immigration"),
    ("transportation", "transportation_parking"),
    ("health_insurance", "health_wellness"),
    ("student_organizations", "student_organizations_engagement"),
    ("academic_calendar", "academic_calendar_graduation"),
    ("accessibility", "accessibility_disability_support"),
)


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("documents", sa.Column("subtopic", sa.String(length=255), nullable=True))
    op.add_column(
        "documents",
        sa.Column(
            "source_role",
            sa.Enum(
                "policy",
                "deadline",
                "procedure",
                "course",
                "program",
                "service",
                "directory",
                "news",
                "historical",
                "reference",
                name="sourcerole",
                native_enum=False,
                length=32,
            ),
            nullable=True,
        ),
    )
    op.add_column("documents", sa.Column("authority_score", sa.Integer(), nullable=True))
    op.add_column("documents", sa.Column("retrieval_priority", sa.Integer(), nullable=True))
    op.add_column(
        "documents",
        sa.Column(
            "temporal_scope",
            sa.Enum(
                "current",
                "historical",
                "archive",
                "unspecified",
                name="temporalscope",
                native_enum=False,
                length=32,
            ),
            nullable=True,
        ),
    )
    op.add_column("documents", sa.Column("academic_year", sa.String(length=16), nullable=True))
    op.add_column(
        "documents",
        sa.Column(
            "index_status",
            sa.Enum(
                "approved",
                "review",
                "blocked",
                "deprecated",
                name="indexstatus",
                native_enum=False,
                length=16,
            ),
            server_default=sa.text("'approved'"),
            nullable=False,
        ),
    )
    op.add_column("documents", sa.Column("embedding_version", sa.String(length=64), nullable=True))
    op.add_column("documents", sa.Column("http_status", sa.Integer(), nullable=True))
    op.add_column("documents", sa.Column("word_count", sa.Integer(), nullable=True))

    op.add_column(
        "document_chunks",
        sa.Column("section_index", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.add_column("document_chunks", sa.Column("parent_text", sa.Text(), nullable=True))

    # Data migration: remap every existing Document.topic value to the new taxonomy. Done with
    # plain UPDATE statements (topic is a native_enum=False VARCHAR column, so this is a data
    # change, not a DDL one -- no ALTER TYPE involved).
    documents = sa.table("documents", sa.column("topic", sa.String), sa.column("index_status", sa.String))
    for old_value, new_value in _TOPIC_RENAMES:
        op.execute(
            documents.update()
            .where(documents.c.topic == old_value)
            .values(topic=new_value)
        )
    # course_registration: temporary defensible default + flagged for the classifier-driven
    # follow-up pass (scripts/remap_topics_v2.py) -- see module docstring.
    op.execute(
        documents.update()
        .where(documents.c.topic == "course_registration")
        .values(topic="campus_services_facilities", index_status="review")
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Note: the topic data remap above is NOT reversed here -- reversing it would require
    # reconstructing which new-taxonomy rows originally came from which old topic, information
    # this migration doesn't separately record (the whole point of a 1:1 rename is that no
    # information is lost forward, but that's a one-way guarantee). A downgrade after this
    # migration has run restores the OLD schema shape but leaves NEW-taxonomy topic values in
    # place, which will not validate against the old Topic enum until application code is also
    # rolled back to match -- schema and application code must be rolled back together here.
    op.drop_column("document_chunks", "parent_text")
    op.drop_column("document_chunks", "section_index")
    op.drop_column("documents", "word_count")
    op.drop_column("documents", "http_status")
    op.drop_column("documents", "embedding_version")
    op.drop_column("documents", "index_status")
    op.drop_column("documents", "academic_year")
    op.drop_column("documents", "temporal_scope")
    op.drop_column("documents", "retrieval_priority")
    op.drop_column("documents", "authority_score")
    op.drop_column("documents", "source_role")
    op.drop_column("documents", "subtopic")
