"""One-off backfill: re-chunk every existing HTML Document with the new
SemanticChunker so `subtopic` and heading-aware chunk boundaries get
populated for the corpus ingested before this phase.

Unlike backfill_document_metadata.py, this CANNOT work from already-
persisted data: ExtractedDocument.sections only exists transiently during
a fresh parse_html() call and was never stored anywhere. Each document is
therefore re-fetched over the network (same cost profile as a full,
non-incremental scripts/run_ingestion.py run) via
IngestionService.rechunk_document, which reuses the exact same
fetch/parse/chunk code the normal ingestion path uses.

PDF documents are skipped: SemanticChunker's PDF-fallback output is
byte-identical to the pre-Phase-3 RecursiveCharacterChunker output (no
section structure was ever available for PDFs), so re-fetching them would
cost time/bandwidth for zero behavior change.

Re-embeds/re-indexes every rechunked document immediately after: chunk
content/subtopic changed even though Document.content_hash did not, and
IndexingService.index_document's own skip check only compares
embedded_content_hash to content_hash, not chunk contents -- it would
otherwise silently leave Qdrant serving stale chunks.

Usage (from backend/):
    uv run python -m scripts.backfill_semantic_chunks
"""

import asyncio

from app.core.logging import configure_logging, get_logger
from app.database.session import get_session_factory
from app.ingestion.fetch import build_client
from app.models.document import SourceType
from app.repositories.document_repository import DocumentRepository
from app.repositories.vector_repository import VectorRepository
from app.services.indexing_service import IndexingService
from app.services.ingestion_service import IngestionService

configure_logging()
logger = get_logger(__name__)

# Large enough to cover the whole corpus in one page -- this is a one-off
# maintenance script, not a paginated API endpoint.
_ALL_DOCUMENTS_LIMIT = 100_000


async def main() -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        repository = DocumentRepository(session)
        vector_repository = VectorRepository()
        await vector_repository.ensure_collection()
        ingestion_service = IngestionService(repository)
        indexing_service = IndexingService(repository, vector_repository)

        documents = await repository.list_documents(limit=_ALL_DOCUMENTS_LIMIT, offset=0)
        html_documents = [d for d in documents if d.source_type is SourceType.HTML]

        rechunked = reindexed = failed = 0
        async with build_client() as client:
            for document in html_documents:
                result = await ingestion_service.rechunk_document(document, http_client=client)
                if result.status == "failed":
                    failed += 1
                    logger.warning("backfill_rechunk_failed", url=document.url, error=result.error)
                    continue
                rechunked += 1

                # Reload to pick up the chunks rechunk_document just
                # committed (replace_chunks doesn't mutate the in-memory
                # .chunks relationship on `document`), THEN force a
                # reindex -- must happen in this order, since reloading
                # afterward would silently discard the override.
                fresh = await repository.get_by_id(document.id)
                if fresh is None:
                    continue
                fresh.embedded_content_hash = None
                index_result = await indexing_service.index_document(fresh)
                if index_result.status == "indexed":
                    reindexed += 1

    logger.info(
        "backfill_semantic_chunks_complete",
        total=len(html_documents),
        rechunked=rechunked,
        reindexed=reindexed,
        failed=failed,
    )


if __name__ == "__main__":
    asyncio.run(main())
