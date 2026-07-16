import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ingestion.sources import SourceConfig
from app.models.conversation_session import StudentType
from app.models.document import Document, DocumentType, SourceType, Topic
from app.repositories.document_repository import DocumentRepository
from app.services.ingestion_service import IngestionService
from tests.ingestion.pdf_helpers import make_pdf_bytes

_HTML_V1 = (
    "<html><head><title>Test Housing Page</title></head>"
    "<body><h1>Test Housing Page</h1>"
    "<p>Freshmen must live on campus during their first year.</p></body></html>"
)
_HTML_V2 = (
    "<html><head><title>Test Housing Page</title></head>"
    "<body><h1>Test Housing Page</h1>"
    "<p>Freshmen must live on campus for two full years now.</p></body></html>"
)
# Has a last-modified meta tag, unlike _HTML_V1/_HTML_V2 -- needed for the
# incremental-mode tests, since a conditional GET is only attempted when
# there's a prior last_updated to send as If-Modified-Since (see
# IngestionService.ingest_source).
_HTML_WITH_LAST_MODIFIED = (
    "<html><head><title>Test Housing Page</title>"
    '<meta name="last-modified" content="2026-03-15T10:00:00+00:00"></head>'
    "<body><h1>Test Housing Page</h1>"
    "<p>Freshmen must live on campus during their first year.</p></body></html>"
)


def _source(
    url: str = "https://example.illinois.edu/housing",
    source_type: SourceType = SourceType.HTML,
) -> SourceConfig:
    return SourceConfig(
        url=url,
        department="Test Department",
        topic=Topic.HOUSING,
        source_type=source_type,
        fallback_title="Fallback Title",
        student_types=(StudentType.FRESHMAN,),
    )


def _mock_client(content: bytes) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=content)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _conditional_mock_client(
    content: bytes, *, requests_seen: list[httpx.Request]
) -> httpx.AsyncClient:
    # Simulates a real conditional-GET-aware server: 304 (no body) when the
    # client sends If-Modified-Since, a normal 200 otherwise.
    def handler(request: httpx.Request) -> httpx.Response:
        requests_seen.append(request)
        if "if-modified-since" in request.headers:
            return httpx.Response(304)
        return httpx.Response(200, content=content)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def _get_with_chunks(repository: DocumentRepository, url: str) -> Document:
    # get_by_url deliberately doesn't eager-load chunks (it's on the hot path
    # for the unchanged-content skip check); go through get_by_id when a test
    # needs to inspect chunks, same as any real caller would.
    summary = await repository.get_by_url(url)
    assert summary is not None
    document = await repository.get_by_id(summary.id)
    assert document is not None
    return document


async def test_ingest_source_creates_new_document_with_chunks(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with db_session_factory() as session:
        repository = DocumentRepository(session)
        service = IngestionService(repository)

        async with _mock_client(_HTML_V1.encode()) as client:
            result = await service.ingest_source(_source(), http_client=client)

        assert result.status == "created"
        assert result.chunk_count >= 1

        document = await _get_with_chunks(repository, _source().url)
        assert document.title == "Test Housing Page"
        assert document.department == "Test Department"
        assert document.topic is Topic.HOUSING
        assert document.student_types == [StudentType.FRESHMAN]
        assert len(document.chunks) == result.chunk_count


async def test_ingest_source_skips_when_content_unchanged(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with db_session_factory() as session:
        service = IngestionService(DocumentRepository(session))

        async with _mock_client(_HTML_V1.encode()) as client:
            first = await service.ingest_source(_source(), http_client=client)
        async with _mock_client(_HTML_V1.encode()) as client:
            second = await service.ingest_source(_source(), http_client=client)

        assert first.status == "created"
        assert second.status == "skipped"


async def test_ingest_source_updates_and_replaces_chunks_when_content_changes(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with db_session_factory() as session:
        repository = DocumentRepository(session)
        service = IngestionService(repository)

        async with _mock_client(_HTML_V1.encode()) as client:
            await service.ingest_source(_source(), http_client=client)
        original = await _get_with_chunks(repository, _source().url)
        original_chunk_ids = {chunk.id for chunk in original.chunks}

        async with _mock_client(_HTML_V2.encode()) as client:
            result = await service.ingest_source(_source(), http_client=client)

        assert result.status == "updated"
        updated = await _get_with_chunks(repository, _source().url)
        assert "two full years" in updated.chunks[0].content
        updated_chunk_ids = {chunk.id for chunk in updated.chunks}
        assert original_chunk_ids.isdisjoint(updated_chunk_ids)


async def test_ingest_source_writes_a_version_row_only_when_content_changes(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with db_session_factory() as session:
        repository = DocumentRepository(session)
        service = IngestionService(repository)

        async with _mock_client(_HTML_V1.encode()) as client:
            await service.ingest_source(_source(), http_client=client)
        original = await _get_with_chunks(repository, _source().url)
        # Captured as plain values, not read back off `original` later --
        # `original` is a live, session-identity-mapped ORM object, so its
        # attributes reflect whatever the row *currently* looks like, not
        # a frozen snapshot from this point in time.
        original_id = original.id
        original_content_hash = original.content_hash
        original_title = original.title
        # No prior version to preserve on first ingestion -- this is a
        # brand-new document, not a content change.
        assert await repository.list_versions(original_id) == []

        # Re-ingesting the exact same content is a no-op (status="skipped"
        # -- see test_ingest_source_skips_when_content_unchanged), so it
        # must not accumulate a version row either.
        async with _mock_client(_HTML_V1.encode()) as client:
            await service.ingest_source(_source(), http_client=client)
        assert await repository.list_versions(original_id) == []

        async with _mock_client(_HTML_V2.encode()) as client:
            await service.ingest_source(_source(), http_client=client)

        versions = await repository.list_versions(original_id)
        assert len(versions) == 1
        # The version row captures what the document *used to* say, not
        # its current content.
        assert versions[0].content_hash == original_content_hash
        assert versions[0].title == original_title


async def test_ingest_source_populates_document_type_keywords_audience_and_last_crawled_at(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with db_session_factory() as session:
        repository = DocumentRepository(session)
        service = IngestionService(repository)

        async with _mock_client(_HTML_V1.encode()) as client:
            await service.ingest_source(_source(), http_client=client)

        document = await _get_with_chunks(repository, _source().url)
        # PROGRAM_DESCRIPTION: neither the URL nor the title/body of
        # _HTML_V1 matches any of classify_document_type's more specific
        # rules -- see test_document_type.py for the rule-by-rule cases.
        assert document.document_type is DocumentType.PROGRAM_DESCRIPTION
        assert len(document.keywords) > 0
        assert document.audience != []
        assert document.last_crawled_at is not None


async def test_ingest_source_updates_last_crawled_at_even_when_content_is_unchanged(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with db_session_factory() as session:
        repository = DocumentRepository(session)
        service = IngestionService(repository)

        async with _mock_client(_HTML_V1.encode()) as client:
            await service.ingest_source(_source(), http_client=client)
        first_crawled_at = (await _get_with_chunks(repository, _source().url)).last_crawled_at
        assert first_crawled_at is not None

        async with _mock_client(_HTML_V1.encode()) as client:
            result = await service.ingest_source(_source(), http_client=client)

        assert result.status == "skipped"
        second_crawled_at = (await _get_with_chunks(repository, _source().url)).last_crawled_at
        assert second_crawled_at is not None
        assert second_crawled_at >= first_crawled_at


async def test_incremental_ingest_sends_no_conditional_header_on_first_ingestion(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    # No existing document yet -- nothing to compare against, so this must
    # be a normal, unconditional fetch regardless of incremental=True.
    async with db_session_factory() as session:
        repository = DocumentRepository(session)
        service = IngestionService(repository)
        requests_seen: list[httpx.Request] = []

        async with _conditional_mock_client(
            _HTML_WITH_LAST_MODIFIED.encode(), requests_seen=requests_seen
        ) as client:
            result = await service.ingest_source(_source(), http_client=client, incremental=True)

        assert result.status == "created"
        assert len(requests_seen) == 1
        assert "if-modified-since" not in requests_seen[0].headers


async def test_incremental_ingest_skips_reparsing_on_304(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with db_session_factory() as session:
        repository = DocumentRepository(session)
        service = IngestionService(repository)

        async with _mock_client(_HTML_WITH_LAST_MODIFIED.encode()) as client:
            await service.ingest_source(_source(), http_client=client)
        first_crawled_at = (await _get_with_chunks(repository, _source().url)).last_crawled_at

        requests_seen: list[httpx.Request] = []
        async with _conditional_mock_client(
            _HTML_WITH_LAST_MODIFIED.encode(), requests_seen=requests_seen
        ) as client:
            result = await service.ingest_source(_source(), http_client=client, incremental=True)

        assert result.status == "skipped"
        # The server saw the conditional header and responded 304 -- the
        # whole point of incremental mode.
        assert "if-modified-since" in requests_seen[0].headers
        second_crawled_at = (await _get_with_chunks(repository, _source().url)).last_crawled_at
        assert second_crawled_at is not None
        assert second_crawled_at >= first_crawled_at


async def test_incremental_ingest_reingests_normally_on_200(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    # The conditional GET's server ignores If-Modified-Since (legal --
    # it's advisory) and returns changed content with 200 instead of 304.
    # Incremental mode must fall through to a full re-ingest, not treat a
    # 200 as "nothing to do."
    async with db_session_factory() as session:
        repository = DocumentRepository(session)
        service = IngestionService(repository)

        async with _mock_client(_HTML_WITH_LAST_MODIFIED.encode()) as client:
            await service.ingest_source(_source(), http_client=client)

        async with _mock_client(_HTML_V2.encode()) as client:
            result = await service.ingest_source(_source(), http_client=client, incremental=True)

        assert result.status == "updated"
        document = await _get_with_chunks(repository, _source().url)
        assert "two full years" in document.chunks[0].content


async def test_ingest_source_handles_pdf_sources(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with db_session_factory() as session:
        repository = DocumentRepository(session)
        service = IngestionService(repository)
        pdf_bytes = make_pdf_bytes(
            "International students must complete SEVIS check-in.", title="I-20 Guide"
        )

        async with _mock_client(pdf_bytes) as client:
            result = await service.ingest_source(
                _source(url="https://example.illinois.edu/i20.pdf", source_type=SourceType.PDF),
                http_client=client,
            )

        assert result.status == "created"
        document = await repository.get_by_url("https://example.illinois.edu/i20.pdf")
        assert document is not None
        assert document.title == "I-20 Guide"
        assert document.source_type is SourceType.PDF


async def test_ingest_source_populates_distinct_subtopics_from_headings(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    # Each section body is repeated well past the production default
    # semantic_chunk_min_section_chars (200) so the two <h2> sections stay
    # distinct chunks instead of merging forward into one another.
    holds_text = "Registration holds must be resolved before you can register. " * 5
    add_drop_text = "The add/drop deadline is the tenth day of the semester. " * 5
    html = (
        "<html><head><title>Registration</title></head><body>"
        "<h1>Registration</h1><p>General registration overview text here.</p>"
        f"<h2>Holds</h2><p>{holds_text}</p>"
        f"<h2>Add/Drop</h2><p>{add_drop_text}</p>"
        "</body></html>"
    )
    async with db_session_factory() as session:
        repository = DocumentRepository(session)
        service = IngestionService(repository)

        async with _mock_client(html.encode()) as client:
            result = await service.ingest_source(_source(), http_client=client)

        assert result.status == "created"
        document = await _get_with_chunks(repository, _source().url)
        subtopics = {chunk.subtopic for chunk in document.chunks}
        assert "Registration > Holds" in subtopics
        assert "Registration > Add/Drop" in subtopics


async def test_ingest_source_pdf_chunks_have_no_subtopic(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with db_session_factory() as session:
        repository = DocumentRepository(session)
        service = IngestionService(repository)
        pdf_bytes = make_pdf_bytes(
            "International students must complete SEVIS check-in.", title="I-20 Guide"
        )

        async with _mock_client(pdf_bytes) as client:
            result = await service.ingest_source(
                _source(url="https://example.illinois.edu/i20-2.pdf", source_type=SourceType.PDF),
                http_client=client,
            )

        assert result.status == "created"
        document = await _get_with_chunks(repository, "https://example.illinois.edu/i20-2.pdf")
        assert len(document.chunks) >= 1
        assert all(chunk.subtopic is None for chunk in document.chunks)


async def test_ingest_source_returns_failed_status_on_fetch_error(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with db_session_factory() as session:
        repository = DocumentRepository(session)
        service = IngestionService(repository)

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, content=b"server error")

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await service.ingest_source(_source(), http_client=client)

        assert result.status == "failed"
        assert result.error is not None

        document = await repository.get_by_url(_source().url)
        assert document is None


async def test_ingest_all_processes_every_source(
    db_session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    async with db_session_factory() as session:
        service = IngestionService(DocumentRepository(session))
        sources = (
            _source(url="https://example.illinois.edu/one"),
            _source(url="https://example.illinois.edu/two"),
        )

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=_HTML_V1.encode())

        # ingest_all builds its own client via app.services.ingestion_service's
        # imported `build_client` name -- patch it there (where it's bound),
        # not on app.ingestion.fetch, so no real network call happens.
        monkeypatch.setattr(
            "app.services.ingestion_service.build_client",
            lambda timeout=15.0: httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        )

        results = await service.ingest_all(sources)

        assert {result.status for result in results} == {"created"}
        assert len(results) == 2
