import enum
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import ARRAY, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database.base import Base
from app.models.conversation_session import StudentType

# Duplicated from app.embeddings.embedder.EMBEDDING_DIMENSION rather than
# imported: that module imports sentence-transformers (and, transitively,
# torch) at module load time, which every consumer of this models module
# (schemas, Alembic migrations, lightweight tests) would otherwise pay for
# just to define a table column. Must stay in sync with EMBEDDING_DIMENSION
# if the embedding model ever changes.
_EMBEDDING_DIMENSION = 384


class Topic(enum.StrEnum):
    """V2 taxonomy (21 topics), migrated from an earlier 24-topic scheme per an external
    "Source Manifest V2" authoritative document. See docs/source-manifest.md and
    backend/scripts/data/source_manifest_v2.md for the taxonomy this was migrated to, and
    backend/scripts/remap_topics_v2.py for how existing rows were reclassified (via
    TopicClassifier against real stored text, not a hand-copied per-URL table -- see that
    script's docstring for why). Some topics carry an optional Document.subtopic (e.g.
    INTERNATIONAL_STUDENTS_IMMIGRATION has OPT/CPT/Visa & Immigration/International Student
    Services subtopics) -- do not confuse this category-level subtopic with
    DocumentChunk.subtopic, which is an unrelated concept (a heading-path within one page).
    """

    ACADEMIC_ADVISING = "academic_advising"
    ACADEMIC_CALENDAR_GRADUATION = "academic_calendar_graduation"
    ACADEMICS = "academics"
    ACCESSIBILITY_DISABILITY_SUPPORT = "accessibility_disability_support"
    ADMISSIONS = "admissions"
    CAMPUS_RECREATION = "campus_recreation"
    CAMPUS_SAFETY = "campus_safety"
    CAMPUS_SERVICES_FACILITIES = "campus_services_facilities"
    CAREER_EMPLOYMENT = "career_employment"
    DINING = "dining"
    FINANCIAL_AID_COSTS = "financial_aid_costs"
    FINANCIAL_AID_SCHOLARSHIPS = "financial_aid_scholarships"
    HEALTH_WELLNESS = "health_wellness"
    HOUSING = "housing"
    INTERNATIONAL_STUDENTS_IMMIGRATION = "international_students_immigration"
    LIBRARIES = "libraries"
    ORIENTATION_NEW_STUDENTS = "orientation_new_students"
    REGISTRATION_RECORDS = "registration_records"
    STUDENT_ORGANIZATIONS_ENGAGEMENT = "student_organizations_engagement"
    TECHNOLOGY_SERVICES = "technology_services"
    TRANSPORTATION_PARKING = "transportation_parking"


class SourceRole(enum.StrEnum):
    """What kind of content a source is -- distinct from DocumentType (which is about
    presentation format: FAQ, form, etc). Drives role-aware chunk sizing (see
    app/ingestion/chunking.py::ROLE_CHUNK_CONFIG) and a retrieval_priority baseline (see
    app/retrieval/priority.py). REVIEW is a deliberate escape hatch: ingestion code that can't
    confidently classify a role leaves this null rather than forcing an inaccurate guess (Source
    Manifest V2, Part 3), and null is treated the same as REFERENCE for chunking/priority
    purposes."""

    POLICY = "policy"
    DEADLINE = "deadline"
    PROCEDURE = "procedure"
    COURSE = "course"
    PROGRAM = "program"
    SERVICE = "service"
    DIRECTORY = "directory"
    NEWS = "news"
    HISTORICAL = "historical"
    REFERENCE = "reference"


class TemporalScope(enum.StrEnum):
    CURRENT = "current"
    HISTORICAL = "historical"
    ARCHIVE = "archive"
    UNSPECIFIED = "unspecified"


class IndexStatus(enum.StrEnum):
    """Governs whether a Document participates in normal retrieval (see
    VectorRepository._filters / HybridRetriever._filter_corpus). Only APPROVED sources are
    returned to users. BLOCKED/DEPRECATED rows are never deleted -- kept for audit/history per
    Source Manifest V2, Part 7."""

    APPROVED = "approved"
    REVIEW = "review"
    BLOCKED = "blocked"
    DEPRECATED = "deprecated"


class SourceType(enum.StrEnum):
    HTML = "html"
    PDF = "pdf"
    # A narrow, source-specific exception, not a general "JSON source" type: every hours page on
    # library.illinois.edu (Main Stacks, Rare Book & Manuscript, Media Commons, SSHEL, the
    # library-hours/ aggregator itself) renders its actual hours client-side via the same
    # WordPress widget, with no server-rendered fallback -- confirmed live, all of them just ship
    # a "Loading Library Hours..." placeholder. The widget's own JS calls a public,
    # unauthenticated JSON API (libdirectory.library.illinois.edu) that already contains the real
    # data, so LIBRARY_HOURS fetches that instead. See app/ingestion/library_hours_loader.py.
    LIBRARY_HOURS = "library_hours"


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
    # Compared against content_hash to decide whether this document's
    # chunks need re-embedding. Separate from content_hash (Phase 3) because ingestion and
    # indexing are independently re-runnable pipeline stages -- a document
    # can be re-fetched with unchanged content (content_hash matches, no
    # reindex needed) or the embedding model can change project-wide
    # (forcing every document to reindex regardless of content_hash).
    embedded_content_hash: Mapped[str | None] = mapped_column(String(64))
    # Category-level subtopic within `topic` (e.g. "OPT" under
    # INTERNATIONAL_STUDENTS_IMMIGRATION) -- distinct from DocumentChunk.subtopic, which is an
    # unrelated per-chunk heading path within one page. Nullable: most topics have no subtopic
    # split, and pages ingested before this column existed have no value until reclassified (see
    # scripts/remap_topics_v2.py).
    subtopic: Mapped[str | None] = mapped_column(String(255))
    # Manifest fields added for Source Manifest V2 (see backend/scripts/data/source_manifest_v2.md).
    # All nullable/defaulted: no value is invented for a source the pipeline can't confidently
    # determine (V2 Part 1's own rule) -- new ingestion runs populate what they reasonably can,
    # existing rows are backfilled by scripts/remap_topics_v2.py where a real signal exists.
    source_role: Mapped[SourceRole | None] = mapped_column(_string_backed_enum(SourceRole, length=32))
    # Computed, not copied from V2's literal per-row values (V2's own authority_score is a flat
    # 10 for ~1000+ of 1069 rows, which would make it useless as the ranking signal it's meant to
    # be) -- see app/retrieval/priority.py for the small, documented formula that derives both
    # from source_type/source_role/temporal_scope instead.
    authority_score: Mapped[int | None] = mapped_column()
    retrieval_priority: Mapped[int | None] = mapped_column()
    temporal_scope: Mapped[TemporalScope | None] = mapped_column(
        _string_backed_enum(TemporalScope, length=32)
    )
    academic_year: Mapped[str | None] = mapped_column(String(16))
    # Governs whether this Document participates in normal retrieval -- see IndexStatus.
    index_status: Mapped[IndexStatus] = mapped_column(
        _string_backed_enum(IndexStatus, length=16), default=IndexStatus.APPROVED
    )
    # Identifies which embedding configuration produced this document's current chunk
    # embeddings, for future embedding-model migrations (Source Manifest V2, Part 8). Set by
    # IndexingService whenever chunks are (re-)embedded; null for chunks embedded before this
    # column existed. Deliberately does NOT trigger any automatic re-embedding by itself --
    # embedded_content_hash already gates that; this is passive identification only.
    embedding_version: Mapped[str | None] = mapped_column(String(64))
    http_status: Mapped[int | None] = mapped_column()
    word_count: Mapped[int | None] = mapped_column()
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

    # No default=uuid.uuid4 (unlike Document.id): chunk IDs are deterministic, computed by
    # app.ingestion.chunk_identity.compute_chunk_id from (document_id, section_index,
    # chunk_number, content) and passed in explicitly by DocumentRepository.replace_chunks. This
    # means re-chunking a document whose text hasn't changed reproduces the exact same chunk IDs
    # instead of churning them on every re-chunk (Source Manifest V2, Part 16).
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
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
    # Index (0-based) of the Section (see app/ingestion/extracted_document.py) this chunk was
    # split from. Chunks sharing (document_id, section_index) are siblings from the same parent
    # section -- this is the "parent" side of parent/child chunking (Source Manifest V2, Part
    # 14), deliberately without a second table or self-referential FK: a section's boundary is
    # already fully described by (document_id, section_index), so no extra row is needed to
    # represent "the parent."
    section_index: Mapped[int] = mapped_column(default=0)
    # Full un-split text of this chunk's parent section, set ONLY when that section had to be
    # split into more than one child chunk (kept null when a chunk IS its whole section, to avoid
    # duplicating storage for the common case). context_builder can expand a matched chunk to its
    # full parent section here when more context is needed, without a second table or re-fetching
    # the source page (Source Manifest V2, Part 14).
    parent_text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    # Set by IndexingService once this chunk's Document has been embedded
    # (null in between: a chunk always exists in Postgres, via
    # DocumentRepository.replace_chunks, before it's ever embedded).
    # Formerly lived only in Qdrant as a separate vector store; folded in
    # here so retrieval is one Postgres query (join + pgvector distance)
    # instead of a Postgres fetch plus a second round-trip to a separate
    # service -- see VectorRepository.
    embedding: Mapped[list[float] | None] = mapped_column(Vector(_EMBEDDING_DIMENSION))

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
