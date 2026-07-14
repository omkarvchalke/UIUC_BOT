import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.conversation_session import StudentType


class SessionCreateRequest(BaseModel):
    student_type: StudentType | None = None
    semester: str | None = None
    college: str | None = None
    department: str | None = None


class SessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    student_type: StudentType | None
    semester: str | None
    college: str | None
    department: str | None
    created_at: datetime
    updated_at: datetime
