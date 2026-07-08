from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import chat, checklist, feedback, retrieve, sources
from app.core.config import get_settings
from app.models.schemas import HealthResponse

settings = get_settings()

app = FastAPI(
    title="CampusGuide AI Backend",
    description="Unofficial RAG assistant for public UIUC new-student information.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/api")
app.include_router(sources.router, prefix="/api")
app.include_router(checklist.router, prefix="/api")
app.include_router(feedback.router, prefix="/api")
app.include_router(retrieve.router, prefix="/api")


@app.get("/health", response_model=HealthResponse, tags=["health"])
def health() -> HealthResponse:
    return HealthResponse(status="healthy", service="campusguide-ai-backend")
