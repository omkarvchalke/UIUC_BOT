"""One-off backfill: populate document_type/keywords/audience for every
Document that predates those columns (added nullable/empty specifically
so this backfill isn't a migration-time blocker -- see the migration's
own comments).

Reuses the exact same classify_document_type/extract_keywords/
infer_audience functions IngestionService now calls for every new
ingestion, so there's one implementation of "what does this metadata
look like," not a second one living only here.

Usage (from backend/):
    uv run python -m scripts.backfill_document_metadata
"""

import asyncio

from app.core.logging import configure_logging, get_logger
from app.database.session import get_session_factory
from app.ingestion.metadata.audience import infer_audience
from app.ingestion.metadata.document_type import classify_document_type
from app.ingestion.metadata.keywords import extract_keywords
from app.repositories.document_repository import DocumentRepository

configure_logging()
logger = get_logger(__name__)

# Large enough to cover the whole corpus in one page -- this is a one-off
# maintenance script, not a paginated API endpoint, so there's no reason
# to chunk the read.
_ALL_DOCUMENTS_LIMIT = 100_000


async def main() -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        repository = DocumentRepository(session)
        documents = await repository.list_documents(limit=_ALL_DOCUMENTS_LIMIT, offset=0)

        updated = 0
        for summary in documents:
            # list_documents doesn't eager-load chunks; re-fetch chunk
            # content for a better keyword signal than the title alone.
            document = await repository.get_by_id(summary.id)
            if document is None:
                continue
            text = "\n\n".join(chunk.content for chunk in document.chunks)

            await repository.upsert_document(
                url=document.url,
                title=document.title,
                department=document.department,
                topic=document.topic,
                source_type=document.source_type,
                student_types=tuple(document.student_types),
                audience=infer_audience(document.url, document.department),
                document_type=classify_document_type(document.url, document.title, text),
                keywords=tuple(extract_keywords(text)),
                last_updated=document.last_updated,
                last_crawled_at=document.last_crawled_at,
                content_hash=document.content_hash,
            )
            updated += 1

        # upsert_document only flushes (see its own docstring/comments in
        # DocumentRepository) -- the regular ingestion flow's commit comes
        # from the replace_chunks call right after it, which this backfill
        # never makes (it doesn't touch chunks). Without an explicit
        # commit here, every change above is silently discarded when the
        # session closes.
        await session.commit()

    logger.info("backfill_document_metadata_complete", total=len(documents), updated=updated)


if __name__ == "__main__":
    asyncio.run(main())
