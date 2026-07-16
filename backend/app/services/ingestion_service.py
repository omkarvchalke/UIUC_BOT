import hashlib
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.ingestion.chunking import ChunkerConfig, RecursiveCharacterChunker
from app.ingestion.extracted_document import ExtractedDocument
from app.ingestion.fetch import FetchError, build_client, fetch_url
from app.ingestion.html_loader import parse_html
from app.ingestion.metadata.audience import infer_audience
from app.ingestion.metadata.document_type import classify_document_type
from app.ingestion.metadata.keywords import extract_keywords
from app.ingestion.pdf_loader import parse_pdf
from app.ingestion.sources import SOURCES, SourceConfig
from app.models.document import SourceType
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
        chunker: RecursiveCharacterChunker | None = None,
    ) -> None:
        self._repository = repository
        if chunker is not None:
            self._chunker = chunker
        else:
            settings = get_settings()
            self._chunker = RecursiveCharacterChunker(
                ChunkerConfig(chunk_size=settings.chunk_size, chunk_overlap=settings.chunk_overlap)
            )

    async def ingest_source(
        self, source: SourceConfig, *, http_client: httpx.AsyncClient | None = None
    ) -> IngestResult:
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

        existing = await self._repository.get_by_url(source.url)
        if existing is not None and existing.content_hash == content_hash:
            # Still worth recording that this URL was checked, even though
            # its content didn't change -- see incremental crawling
            # (scripts/run_crawl.py --incremental), which uses
            # last_crawled_at to decide whether a URL is due for a
            # conditional-GET recheck at all.
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

        chunks = self._chunker.split(extracted.text)
        await self._repository.replace_chunks(document.id, chunks)

        status: IngestStatus = "updated" if existing is not None else "created"
        logger.info(
            "ingestion_source_ingested", url=source.url, status=status, chunk_count=len(chunks)
        )
        return IngestResult(url=source.url, status=status, chunk_count=len(chunks))

    async def ingest_all(self, sources: Iterable[SourceConfig] = SOURCES) -> list[IngestResult]:
        results = []
        async with build_client() as client:
            for source in sources:
                results.append(await self.ingest_source(source, http_client=client))
        return results

    @staticmethod
    def _parse(source: SourceConfig, raw_bytes: bytes) -> ExtractedDocument:
        if source.source_type is SourceType.HTML:
            html = raw_bytes.decode("utf-8", errors="replace")
            return parse_html(html, base_url=source.url, fallback_title=source.fallback_title)
        return parse_pdf(raw_bytes, fallback_title=source.fallback_title)
