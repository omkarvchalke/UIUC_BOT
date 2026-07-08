import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Query

from app.models.schemas import SourceItem, SourceListResponse

router = APIRouter(tags=["sources"])

# backend/app/api/sources.py -> parents[3] is the repo root
SOURCES_PATH = Path(__file__).resolve().parents[3] / "ingestion" / "sources.json"


def _load_sources() -> list[SourceItem]:
    with SOURCES_PATH.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    return [SourceItem(**entry) for entry in raw]


@router.get("/sources", response_model=SourceListResponse)
def get_sources(category: Optional[str] = Query(default=None)) -> SourceListResponse:
    sources = _load_sources()
    if category:
        sources = [s for s in sources if s.category == category]
    return SourceListResponse(sources=sources)
