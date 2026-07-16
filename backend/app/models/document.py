import enum
import uuid
from datetime import datetime

from sqlalchemy import ARRAY, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database.base import Base
from app.models.conversation_session import StudentType


class Topic(enum.StrEnum):
    ADMISSIONS = "admissions"
    REGISTRATION = "registration"
    ORIENTATION = "orientation"
    HOUSING = "housing"
    DINING = "dining"
    FINANCIAL_AID = "financial_aid"
    SCHOLARSHIPS = "scholarships"
    STUDENT_EMPLOYMENT = "student_employment"
    INTERNATIONAL_STUDENT_SERVICES = "international_student_services"
    VISA = "visa"
    CPT = "cpt"
    OPT = "opt"
    TECHNOLOGY_SERVICES = "technology_services"
    LIBRARIES = "libraries"
    TRANSPORTATION = "transportation"
    HEALTH_INSURANCE = "health_insurance"
    CAMPUS_RECREATION = "campus_recreation"
    STUDENT_ORGANIZATIONS = "student_organizations"
    ACADEMIC_CALENDAR = "academic_calendar"
    COURSE_REGISTRATION = "course_registration"
    CAMPUS_SAFETY = "campus_safety"
    ACCESSIBILITY = "accessibility"


class SourceType(enum.StrEnum):
    HTML = "html"
    PDF = "pdf"


class Audience(enum.StrEnum):
    """Who a page is *written for* -- distinct from StudentType (which
    admission category a page applies to). A financial-aid page can be
    audience=[CURRENT_STUDENT, PROSPECTIVE_STUDENT] and independently
    student_types=() (applies to every admission category). Two orthogonal
    filters, not two names for the same thing."""

    PROSPECTIVE_STUDENT = "prospective_student"
    CURRENT_STUDENT = "current_student"
    FACULTY_STAFF = "faculty_staff"
    ALUMNI = "alumni"
    PARENT_FAMILY = "parent_family"
    GENERAL_PUBLIC = "general_public"


class DocumentType(enum.StrEnum):
    """Semantic kind of content -- distinct from SourceType (HTML/PDF,
    file format). A PDF can be a FORM; an HTML page can also be a FORM
    (an embedded web form)."""

    POLICY = "policy"
    FORM = "form"
    FAQ = "faq"
    DEADLINE_REFERENCE = "deadline_reference"
    NEWS_ANNOUNCEMENT = "news_announcement"
    PROGRAM_DESCRIPTION = "program_description"
    HOW_TO_GUIDE = "how_to_guide"
    CONTACT_INFO = "contact_info"


def _string_backed_enum(enum_cls: type[enum.StrEnum], *, length: int) -> SAEnum:
    # native_enum=False: plain VARCHAR + Python-side validation instead of a
    # Postgres CREATE TYPE. Native Postgres enums require an ALTER TYPE ...
    # ADD VALUE migration to extend and can't be used as an ARRAY element
    # without extra ceremony -- a poor fit for a topic/source list that's
    # explicitly meant to grow as more sources are added.
    return SAEnum(
        enum_cls,
        native_enum=False,
        length=length,
        values_callable=lambda cls: [member.value for member in cls],
    )


class Document(Base):
    """A single ingested source (one HTML page or PDF). Chunks belong to it."""

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    url: Mapped[str] = mapped_column(String(2048), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(512))
    department: Mapped[str] = mapped_column(String(255))
    topic: Mapped[Topic] = mapped_column(_string_backed_enum(Topic, length=64))
    source_type: Mapped[SourceType] = mapped_column(_string_backed_enum(SourceType, length=16))
    student_types: Mapped[list[StudentType]] = mapped_column(
        ARRAY(_string_backed_enum(StudentType, length=32)), default=list
    )
    audience: Mapped[list[Audience]] = mapped_column(
        ARRAY(_string_backed_enum(Audience, length=32)), default=list
    )
    # Nullable: ~1000+ existing rows predate this column and have no value
    # until scripts/backfill_document_metadata.py runs. New rows from
    # ingestion always get a real value (see IngestionService/Crawler), so
    # this is effectively non-null going forward even though the DB allows
    # it -- a NOT NULL constraint would have required backfilling inside
    # the migration transaction itself, coupling a classifier's behavior to
    # a one-time DDL change instead of the same tested pipeline code.
    document_type: Mapped[DocumentType | None] = mapped_column(
        _string_backed_enum(DocumentType, length=32)
    )
    keywords: Mapped[list[str]] = mapped_column(ARRAY(String(100)), default=list)
    last_updated: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Set on every successful crawl/ingest of this URL -- distinct from
    # updated_at (which also changes on, e.g., a re-index-only touch).
    # Powers incremental crawling: a conditional GET only makes sense once
    # we know when a URL was last actually checked.
    last_crawled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    content_hash: Mapped[str] = mapped_column(String(64))
    # Compared against content_hash to decide whether Qdrant needs
    # re-indexing. Separate from content_hash (Phase 3) because ingestion and
    # indexing are independently re-runnable pipeline stages -- a document
    # can be re-fetched with unchanged content (content_hash matches, no
    # reindex needed) or the embedding model can change project-wide
    # (forcing every document to reindex regardless of content_hash).
    embedded_content_hash: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentChunk.chunk_number",
    )
    versions: Mapped[list["DocumentVersion"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentVersion.captured_at",
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (UniqueConstraint("document_id", "chunk_number"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    chunk_number: Mapped[int]
    content: Mapped[str] = mapped_column(Text)
    char_count: Mapped[int]
    # Which section of the source document this chunk came from (e.g.
    # "Registration Holds" on a Registrar page with many sibling sections).
    # Nullable: populated by the semantic chunker, not this phase -- see
    # app/ingestion/chunking.py's module docstring for the phase boundary.
    subtopic: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    document: Mapped[Document] = relationship(back_populates="chunks")


class DocumentVersion(Base):
    """Append-only audit trail of a Document's previous content, written
    just before an upsert overwrites Document with new content (see
    DocumentRepository.upsert_document). Not a duplicate of current
    content -- only written when content_hash is about to change, so a
    document that never changes accumulates zero version rows."""

    __tablename__ = "document_versions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    content_hash: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(512))
    captured_at: Mapped[datetime] = mapped_column(server_default=func.now())

    document: Mapped[Document] = relationship(back_populates="versions")
