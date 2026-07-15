from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import FeedbackServiceDep
from app.core.exceptions import SessionNotFoundError
from app.schemas.feedback import FeedbackCreateRequest, FeedbackResponse

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
async def submit_feedback(
    payload: FeedbackCreateRequest, service: FeedbackServiceDep
) -> FeedbackResponse:
    try:
        feedback = await service.submit_feedback(
            session_id=payload.session_id,
            message_id=payload.message_id,
            question=payload.question,
            answer=payload.answer,
            rating=payload.rating,
            comment=payload.comment,
        )
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return FeedbackResponse.model_validate(feedback)
