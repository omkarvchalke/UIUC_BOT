import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter

from app.models.schemas import FeedbackRequest, FeedbackResponse

router = APIRouter(tags=["feedback"])

# backend/app/api/feedback.py -> parents[2] is backend/
FEEDBACK_DIR = Path(__file__).resolve().parents[2] / "data"
FEEDBACK_PATH = FEEDBACK_DIR / "feedback.jsonl"


@router.post("/feedback", response_model=FeedbackResponse)
def submit_feedback(request: FeedbackRequest) -> FeedbackResponse:
    FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
    record = request.model_dump()
    record["timestamp"] = datetime.now(timezone.utc).isoformat()
    with FEEDBACK_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    return FeedbackResponse(status="received")
