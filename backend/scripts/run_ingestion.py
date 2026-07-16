"""Run the document ingestion pipeline against the configured source manifest.

Usage (from backend/):
    uv run python -m scripts.run_ingestion
    uv run python -m scripts.run_ingestion --incremental

--incremental: for a source already in the corpus with a known
last_updated, sends a conditional GET (If-Modified-Since) instead of a
full fetch -- a 304 response skips parsing/hashing entirely. Costs one
small request per unchanged page instead of a full fetch, at the cost of
trusting whatever last-modified signal the source publishes (many UIUC
pages don't publish one at all, see html_loader.py's meta-tag/<time>
extraction -- those sources always fall back to a full fetch regardless
of this flag). A full (non-incremental) run remains the default and is
still the only way to detect a change on a source with no reliable
last-modified signal.
"""

import argparse
import asyncio

from app.core.logging import configure_logging, get_logger
from app.database.session import get_session_factory
from app.repositories.document_repository import DocumentRepository
from app.services.ingestion_service import IngestionService, IngestResult

configure_logging()
logger = get_logger(__name__)


async def main(*, incremental: bool = False) -> list[IngestResult]:
    # Each source commits its own document+chunks atomically inside
    # DocumentRepository.replace_chunks (or, for an incremental skip,
    # inside DocumentRepository.touch_last_crawled) -- no outer commit
    # needed here.
    session_factory = get_session_factory()
    async with session_factory() as session:
        service = IngestionService(DocumentRepository(session))
        results = await service.ingest_all(incremental=incremental)

    counts: dict[str, int] = {}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1
        if result.status == "failed":
            logger.warning("ingestion_failed", url=result.url, error=result.error)

    logger.info("ingestion_run_complete", total=len(results), incremental=incremental, **counts)
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--incremental",
        action="store_true",
        help="Use a conditional GET for sources with a known last_updated.",
    )
    args = parser.parse_args()
    asyncio.run(main(incremental=args.incremental))
