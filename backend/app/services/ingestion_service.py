import hashlib
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

import httpx

from app.core.logging import get_logger
from app.ingestion.chunking import RecursiveCharacterChunker
from app.ingestion.extracted_document import ExtractedDocument
from app.ingestion.fetch import FetchError, build_client, fetch_url
from app.ingestion.html_loader import parse_html
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
        self._chunker = chunker or RecursiveCharacterChunker()

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
            logger.info("ingestion_source_unchanged", url=source.url)
            return IngestResult(url=source.url, status="skipped")

        document = await self._repository.upsert_document(
            url=source.url,
            title=extracted.title or source.fallback_title,
            department=source.department,
            topic=source.topic,
            source_type=source.source_type,
            student_types=source.student_types,
            last_updated=extracted.last_updated,
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
            return parse_html(html, fallback_title=source.fallback_title)
        return parse_pdf(raw_bytes, fallback_title=source.fallback_title)
