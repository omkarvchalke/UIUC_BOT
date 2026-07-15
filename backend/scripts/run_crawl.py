"""Discover new sources by crawling bounded sections of the sites already
represented in app/ingestion/sources.py, then ingest the ones that pass a
basic quality bar the same way manifest sources are ingested.

This does NOT replace the manifest -- accepted pages are ingested into the
same documents table via the same IngestionService used by
scripts/run_ingestion.py, so re-running ingestion later still works
identically for them (hash-based skip, etc.). It also does NOT run
embeddings/indexing or the golden-set eval; run those as separate,
explicit steps afterward so a bad crawl is easy to inspect before it
affects retrieval.

Usage (from backend/):
    uv run python -m scripts.run_crawl
    uv run python -m scripts.run_ingestion   # if you skip auto-ingest below
    uv run python -m scripts.run_indexing
    uv run python -m scripts.eval_answers    # verify answer quality didn't regress
"""

import asyncio

from app.core.logging import configure_logging, get_logger
from app.database.session import get_session_factory
from app.ingestion.crawl_seeds import CRAWL_SEEDS
from app.ingestion.crawler import Crawler
from app.ingestion.sources import SourceConfig
from app.repositories.document_repository import DocumentRepository
from app.services.ingestion_service import IngestionService

configure_logging()
logger = get_logger(__name__)


def _print_report(accepted: list[SourceConfig], rejected: list[tuple[str, str]]) -> None:
    print(f"\n{len(accepted)} pages accepted:")
    for source in accepted:
        types = ", ".join(t.value for t in source.student_types) or "everyone"
        print(f"  [{source.topic.value:25} | {types:15}] {source.url}")
        print(f"    {source.fallback_title}")

    print(f"\n{len(rejected)} pages rejected:")
    reasons: dict[str, int] = {}
    for _, reason in rejected:
        key = reason.split(" (")[0].split(":")[0]
        reasons[key] = reasons.get(key, 0) + 1
    for reason, count in sorted(reasons.items(), key=lambda kv: -kv[1]):
        print(f"  {count:4} x {reason}")


async def main() -> None:
    crawler = Crawler()
    outcome = await crawler.crawl(CRAWL_SEEDS)
    _print_report(outcome.accepted, outcome.rejected)

    if not outcome.accepted:
        print("\nNothing new to ingest.")
        return

    session_factory = get_session_factory()
    async with session_factory() as session:
        service = IngestionService(DocumentRepository(session))
        results = await service.ingest_all(outcome.accepted)

    counts: dict[str, int] = {}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1
    logger.info("crawl_ingestion_complete", total=len(results), **counts)

    print(
        "\nIngested. Next: `uv run python -m scripts.run_indexing`, then "
        "`uv run python -m scripts.eval_answers` to check answer quality didn't regress."
    )


if __name__ == "__main__":
    asyncio.run(main())
