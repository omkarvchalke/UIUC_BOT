import hashlib
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.ingestion.chunking import ChunkerConfig
from app.ingestion.extracted_document import ExtractedDocument
from app.ingestion.fetch import FetchError, build_client, fetch_response, fetch_url
from app.ingestion.html_loader import parse_html
from app.ingestion.metadata.audience import infer_audience
from app.ingestion.metadata.document_type import classify_document_type
from app.ingestion.metadata.keywords import extract_keywords
from app.ingestion.pdf_loader import parse_pdf
from app.ingestion.semantic_chunker import SemanticChunker
from app.ingestion.sources import SOURCES, SourceConfig
from app.models.document import Document, SourceType
from app.repositories.document_repository import DocumentRepository

logger = get_logger(__name__)

IngestStatus = Literal["created", "updated", "skipped", "failed"]


@dataclass(frozen=True)
class IngestResult:
    url: str
    status: IngestStatus
    chunk_count: int = 0
    error: str | None = None


class IngestionService:
    """Orchestrates fetch -> parse -> clean -> chunk -> persist for the source manifest.

    Re-running ingestion is safe and cheap: each source's cleaned text is
    hashed, and a source is skipped (no re-chunk, no DB write) when the hash
    matches what's already stored, so a scheduled re-ingestion only does work
    for pages that actually changed.
    """

    def __init__(
        self,
        repository: DocumentRepository,
        *,
        chunker: SemanticChunker | None = None,
    ) -> None:
        self._repository = repository
        if chunker is not None:
            self._chunker = chunker
        else:
            settings = get_settings()
            self._chunker = SemanticChunker(
                ChunkerConfig(chunk_size=settings.chunk_size, chunk_overlap=settings.chunk_overlap)
            )

    async def ingest_source(
        self,
        source: SourceConfig,
        *,
        http_client: httpx.AsyncClient | None = None,
        incremental: bool = False,
    ) -> IngestResult:
        existing = await self._repository.get_by_url(source.url)

        # incremental (scripts/run_ingestion.py --incremental): a
        # conditional GET using the stored last_updated, so an unchanged
        # page costs one small request instead of a full fetch + parse +
        # hash + compare. Only possible when there's a prior last_updated
        # to compare against -- a source with none (many pages don't
        # publish a last-modified signal at all, see html_loader.py) always
        # falls through to a normal full fetch below.
        if incremental and existing is not None and existing.last_updated is not None:
            try:
                probe = await fetch_response(
                    source.url, client=http_client, if_modified_since=existing.last_updated
                )
            except FetchError as exc:
                logger.warning("ingestion_fetch_failed", url=source.url, error=str(exc))
                return IngestResult(url=source.url, status="failed", error=str(exc))
            if probe.status_code == 304:
                await self._repository.touch_last_crawled(existing.id)
                logger.info("ingestion_source_not_modified", url=source.url)
                return IngestResult(url=source.url, status="skipped")
            # 200: genuinely modified (or the server ignored the
            # conditional header, which is legal -- If-Modified-Since is
            # advisory). Reuse this response's body instead of fetching
            # the same URL a second time.
            raw_bytes = probe.content
        else:
            try:
                raw_bytes = await fetch_url(source.url, client=http_client)
            except FetchError as exc:
                logger.warning("ingestion_fetch_failed", url=source.url, error=str(exc))
                return IngestResult(url=source.url, status="failed", error=str(exc))

        try:
            extracted = self._parse(source, raw_bytes)
        except Exception as exc:  # noqa: BLE001 - one bad source must not abort the batch
            logger.warning("ingestion_parse_failed", url=source.url, error=str(exc))
            return IngestResult(url=source.url, status="failed", error=str(exc))

        if not extracted.text:
            logger.warning("ingestion_empty_text", url=source.url)
            return IngestResult(url=source.url, status="failed", error="no extractable text")

        content_hash = hashlib.sha256(extracted.text.encode("utf-8")).hexdigest()

        if existing is not None and existing.content_hash == content_hash:
            # Still worth recording that this URL was checked, even though
            # its content didn't change (e.g. the server ignored the
            # conditional header above, or this was a non-incremental run).
            await self._repository.touch_last_crawled(existing.id)
            logger.info("ingestion_source_unchanged", url=source.url)
            return IngestResult(url=source.url, status="skipped")

        title = extracted.title or source.fallback_title
        # Computed fresh from this fetch's own parsed content every time,
        # for both the manifest and crawler-discovered paths -- Crawler's
        # own parse (at discovery time) doesn't carry through to here (only
        # url/department/topic/source_type/fallback_title/student_types do,
        # same as before this phase), and re-deriving from the text
        # actually being persisted is more reliable than trusting a value
        # computed against a possibly-earlier fetch of the same page.
        document = await self._repository.upsert_document(
            url=source.url,
            title=title,
            department=source.department,
            topic=source.topic,
            source_type=source.source_type,
            student_types=source.student_types,
            audience=infer_audience(source.url, source.department),
            document_type=classify_document_type(source.url, title, extracted.text),
            keywords=tuple(extract_keywords(extracted.text)),
            last_updated=extracted.last_updated,
            last_crawled_at=datetime.now(UTC),
            content_hash=content_hash,
        )

        chunk_results = self._chunker.split(extracted)
        await self._repository.replace_chunks(document.id, chunk_results)

        status: IngestStatus = "updated" if existing is not None else "created"
        logger.info(
            "ingestion_source_ingested",
            url=source.url,
            status=status,
            chunk_count=len(chunk_results),
        )
        return IngestResult(url=source.url, status=status, chunk_count=len(chunk_results))

    async def ingest_all(
        self, sources: Iterable[SourceConfig] = SOURCES, *, incremental: bool = False
    ) -> list[IngestResult]:
        results = []
        async with build_client() as client:
            for source in sources:
                results.append(
                    await self.ingest_source(source, http_client=client, incremental=incremental)
                )
        return results

    async def rechunk_document(
        self, document: Document, *, http_client: httpx.AsyncClient | None = None
    ) -> IngestResult:
        """Re-fetches document.url, re-parses, and replaces its chunks with
        fresh SemanticChunker output -- without touching Document metadata
        (title/topic/audience/content_hash/etc). Used only by
        scripts/backfill_semantic_chunks.py: existing chunks predate this
        phase's heading-aware chunker and were never re-chunked by a normal
        content-unchanged re-ingestion run (ingest_source above skips
        chunking entirely when content_hash matches)."""
        source = SourceConfig(
            url=document.url,
            department=document.department,
            topic=document.topic,
            source_type=document.source_type,
            fallback_title=document.title,
            student_types=tuple(document.student_types),
        )
        try:
            raw_bytes = await fetch_url(source.url, client=http_client)
        except FetchError as exc:
            logger.warning("rechunk_fetch_failed", url=source.url, error=str(exc))
            return IngestResult(url=source.url, status="failed", error=str(exc))

        try:
            extracted = self._parse(source, raw_bytes)
        except Exception as exc:  # noqa: BLE001 - one bad document must not abort the batch
            logger.warning("rechunk_parse_failed", url=source.url, error=str(exc))
            return IngestResult(url=source.url, status="failed", error=str(exc))

        chunk_results = self._chunker.split(extracted)
        await self._repository.replace_chunks(document.id, chunk_results)
        logger.info("rechunk_document_rechunked", url=source.url, chunk_count=len(chunk_results))
        return IngestResult(url=source.url, status="updated", chunk_count=len(chunk_results))

    @staticmethod
    def _parse(source: SourceConfig, raw_bytes: bytes) -> ExtractedDocument:
        if source.source_type is SourceType.HTML:
            html = raw_bytes.decode("utf-8", errors="replace")
            return parse_html(html, base_url=source.url, fallback_title=source.fallback_title)
        return parse_pdf(raw_bytes, fallback_title=source.fallback_title)
