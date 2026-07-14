"""Embed ingested documents and upsert them into Qdrant.

Usage (from backend/):
    uv run python -m scripts.run_indexing
"""

import asyncio

from app.core.logging import configure_logging, get_logger
from app.database.session import get_session_factory
from app.repositories.document_repository import DocumentRepository
from app.repositories.vector_repository import VectorRepository
from app.services.indexing_service import IndexingService, IndexResult

configure_logging()
logger = get_logger(__name__)


async def main() -> list[IndexResult]:
    session_factory = get_session_factory()
    async with session_factory() as session:
        service = IndexingService(DocumentRepository(session), VectorRepository())
        results = await service.index_all()

    counts: dict[str, int] = {}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1
        if result.status == "failed":
            logger.warning("indexing_failed", url=result.url, error=result.error)

    logger.info("indexing_run_complete", total=len(results), **counts)
    return results


if __name__ == "__main__":
    asyncio.run(main())
