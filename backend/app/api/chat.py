import time

from fastapi import APIRouter, Request

from app.api.dependencies import AnalyticsServiceDep, CompiledGraphDep
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.rate_limit import limiter
from app.graph.graph import config_for, turn_input
from app.models.chat_turn_event import ChatTurnIntent
from app.schemas.chat import ChatCitation, ChatRequest, ChatResponse

logger = get_logger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
@limiter.limit(lambda: get_settings().chat_rate_limit)
async def chat(
    request: Request,
    payload: ChatRequest,
    graph: CompiledGraphDep,
    analytics: AnalyticsServiceDep,
) -> ChatResponse:
    start = time.perf_counter()
    result = await graph.ainvoke(
        turn_input(payload.session_id, payload.message),
        config=config_for(payload.session_id),
    )
    latency_ms = (time.perf_counter() - start) * 1000

    try:
        await analytics.record_turn(
            session_id=payload.session_id,
            intent=ChatTurnIntent(result.get("intent", "question")),
            topic=result.get("topic"),
            needs_clarification=result.get("needs_clarification", False),
            grounded=result.get("grounded"),
            citation_count=len(result.get("citations", [])),
            latency_ms=latency_ms,
        )
    except Exception as exc:  # noqa: BLE001 - analytics must never break the chat response
        logger.warning(
            "analytics_record_turn_failed", session_id=str(payload.session_id), error=str(exc)
        )

    return ChatResponse(
        answer=result["answer"],
        grounded=result.get("grounded", False),
        needs_clarification=result.get("needs_clarification", False),
        citations=[ChatCitation(**citation) for citation in result.get("citations", [])],
        topic=result.get("topic"),
        classification_confidence=result.get("classification_confidence"),
    )
