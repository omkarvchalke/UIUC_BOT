import uuid

from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import SessionServiceDep
from app.core.exceptions import SessionNotFoundError
from app.schemas.session import SessionCreateRequest, SessionResponse

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    payload: SessionCreateRequest, service: SessionServiceDep
) -> SessionResponse:
    session = await service.create_session(
        student_type=payload.student_type,
        semester=payload.semester,
        college=payload.college,
        department=payload.department,
    )
    return SessionResponse.model_validate(session)


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(session_id: uuid.UUID, service: SessionServiceDep) -> SessionResponse:
    try:
        session = await service.get_session(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return SessionResponse.model_validate(session)
