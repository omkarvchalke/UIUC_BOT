from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Query

from app.api.dependencies import AnalyticsServiceDep
from app.schemas.analytics import AnalyticsSummary

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/summary", response_model=AnalyticsSummary)
async def get_summary(
    service: AnalyticsServiceDep,
    days: int | None = Query(default=30, ge=1, le=365),
) -> AnalyticsSummary:
    # created_at columns across this app (ConversationSession, Feedback,
    # ChatTurnEvent) are all naive DateTime -- populated by Postgres's
    # func.now() -- so `since` must be naive too, not tz-aware, or asyncpg
    # raises "can't subtract offset-naive and offset-aware datetimes".
    since = (datetime.now(UTC) - timedelta(days=days)).replace(tzinfo=None) if days else None
    return await service.get_summary(since=since)
