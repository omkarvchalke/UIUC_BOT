import enum
import uuid
from datetime import datetime

from sqlalchemy import Enum as SAEnum
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database.base import Base


class StudentType(enum.StrEnum):
    FRESHMAN = "freshman"
    TRANSFER = "transfer"
    GRADUATE = "graduate"
    INTERNATIONAL = "international"


_student_type_enum = SAEnum(
    StudentType,
    name="student_type",
    values_callable=lambda enum_cls: [e.value for e in enum_cls],
)


class ConversationSession(Base):
    """Anonymous session state. Deliberately holds no PII (no name, email, UIN, phone)."""

    __tablename__ = "conversation_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    student_type: Mapped[StudentType | None] = mapped_column(_student_type_enum)
    semester: Mapped[str | None] = mapped_column(String(50))
    college: Mapped[str | None] = mapped_column(String(255))
    department: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
