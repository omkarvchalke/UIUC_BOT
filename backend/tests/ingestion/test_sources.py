from app.ingestion.sources import SOURCES


def test_manifest_is_not_empty() -> None:
    assert len(SOURCES) > 0


def test_all_urls_are_https_and_on_the_illinois_edu_domain() -> None:
    for source in SOURCES:
        assert source.url.startswith("https://"), source.url
        assert ".illinois.edu" in source.url, source.url


def test_all_urls_are_unique() -> None:
    urls = [source.url for source in SOURCES]
    assert len(urls) == len(set(urls))


def test_every_source_has_department_and_fallback_title() -> None:
    for source in SOURCES:
        assert source.department.strip()
        assert source.fallback_title.strip()


def test_pdf_sources_point_at_pdf_urls() -> None:
    from app.models.document import SourceType

    for source in SOURCES:
        if source.source_type is SourceType.PDF:
            assert source.url.lower().endswith(".pdf"), source.url
