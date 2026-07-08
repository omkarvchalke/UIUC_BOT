from typing import Literal, Optional

from pydantic import BaseModel, Field

# --- Health ---


class HealthResponse(BaseModel):
    status: str
    service: str


# --- Chat ---


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1)
    history: list[ChatTurn] = Field(default_factory=list, max_length=20)


class SourceRef(BaseModel):
    title: str
    url: str
    category: str
    department: str


ConfidenceLevel = Literal["high", "medium", "low"]


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceRef] = Field(default_factory=list)
    confidence: ConfidenceLevel
    next_steps: list[str] = Field(default_factory=list)
    requires_official_confirmation: bool = False


# --- Retrieve ---


class RetrieveRequest(BaseModel):
    question: str = Field(..., min_length=1)


class RetrievedChunk(BaseModel):
    chunk_text: str
    source_title: str
    source_url: str
    category: str
    department: str
    score: float


class RetrieveResponse(BaseModel):
    results: list[RetrievedChunk]


# --- Sources ---


class SourceItem(BaseModel):
    title: str
    category: str
    department: str
    url: str
    source_type: str


class SourceListResponse(BaseModel):
    sources: list[SourceItem]


# --- Checklist ---

StudentType = Literal["freshman", "transfer", "graduate"]
StudentStatus = Literal["domestic", "international"]
Term = Literal["fall", "spring"]
Housing = Literal["on-campus", "off-campus", "not sure"]


class ChecklistRequest(BaseModel):
    student_type: StudentType
    student_status: StudentStatus
    term: Term
    housing: Housing


class ChecklistItem(BaseModel):
    task: str
    source_title: Optional[str] = None
    source_url: Optional[str] = None


class ChecklistSection(BaseModel):
    title: str
    items: list[ChecklistItem]


class ChecklistResponse(BaseModel):
    disclaimer: str
    sections: list[ChecklistSection]


# --- Feedback ---

FeedbackRating = Literal["helpful", "not_helpful", "wrong_source", "missing_information"]


class FeedbackRequest(BaseModel):
    question: str
    answer: str
    rating: FeedbackRating
    comment: Optional[str] = None
    source_titles: list[str] = Field(default_factory=list)


class FeedbackResponse(BaseModel):
    status: str
