from fastapi import APIRouter, Request

from app.api.dependencies import CompiledGraphDep
from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.graph.graph import config_for, turn_input
from app.schemas.chat import ChatCitation, ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
@limiter.limit(lambda: get_settings().chat_rate_limit)
async def chat(request: Request, payload: ChatRequest, graph: CompiledGraphDep) -> ChatResponse:
    result = await graph.ainvoke(
        turn_input(payload.session_id, payload.message),
        config=config_for(payload.session_id),
    )

    return ChatResponse(
        answer=result["answer"],
        grounded=result.get("grounded", False),
        needs_clarification=result.get("needs_clarification", False),
        citations=[ChatCitation(**citation) for citation in result.get("citations", [])],
    )
