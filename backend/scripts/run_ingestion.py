"""Run the document ingestion pipeline against the configured source manifest.

Usage (from backend/):
    uv run python -m scripts.run_ingestion
"""

import asyncio

from app.core.logging import configure_logging, get_logger
from app.database.session import get_session_factory
from app.repositories.document_repository import DocumentRepository
from app.services.ingestion_service import IngestionService, IngestResult

configure_logging()
logger = get_logger(__name__)


async def main() -> list[IngestResult]:
    # Each source commits its own document+chunks atomically inside
    # DocumentRepository.replace_chunks, so no outer commit is needed here.
    session_factory = get_session_factory()
    async with session_factory() as session:
        service = IngestionService(DocumentRepository(session))
        results = await service.ingest_all()

    counts: dict[str, int] = {}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1
        if result.status == "failed":
            logger.warning("ingestion_failed", url=result.url, error=result.error)

    logger.info("ingestion_run_complete", total=len(results), **counts)
    return results


if __name__ == "__main__":
    asyncio.run(main())
