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


class SourceType(enum.StrEnum):
    HTML = "html"
    PDF = "pdf"


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
    last_updated: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    content_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentChunk.chunk_number",
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
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    document: Mapped[Document] = relationship(back_populates="chunks")
