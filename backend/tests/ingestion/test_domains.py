"""Safety net for the Knowledge Domain folder reorganization: every entry
that used to live in the old, single-file `crawl_seeds.py`/`sources.py`
must still be reachable from exactly one `app/ingestion/domains/*` module,
and the flat `CRAWL_SEEDS`/`SOURCES` re-exports must still line up with
the aggregated `domains` package.
"""

from app.ingestion import crawl_seeds, domains, sources


def test_all_seeds_come_from_exactly_one_domain_module() -> None:
    seen: dict[str, str] = {}
    for module in domains._MODULES:
        for seed in module.SEEDS:
            assert seed.start_url not in seen, (
                f"{seed.start_url} claimed by both {seen[seed.start_url]} and {module.__name__}"
            )
            seen[seed.start_url] = module.__name__
    assert len(seen) == len(domains.ALL_SEEDS)


def test_all_sources_come_from_exactly_one_domain_module() -> None:
    seen: dict[str, str] = {}
    for module in domains._MODULES:
        for source in module.SOURCES:
            assert source.url not in seen, (
                f"{source.url} claimed by both {seen[source.url]} and {module.__name__}"
            )
            seen[source.url] = module.__name__
    assert len(seen) == len(domains.ALL_SOURCES)


def test_crawl_seeds_reexport_matches_domains_aggregate() -> None:
    assert crawl_seeds.CRAWL_SEEDS == domains.ALL_SEEDS


def test_sources_reexport_matches_domains_aggregate() -> None:
    assert sources.SOURCES == domains.ALL_SOURCES


def test_expected_entry_counts() -> None:
    # Pins the counts verified against the pre-reorganization snapshot --
    # a silent drop or duplicate during a future domain-file edit changes
    # one of these numbers.
    assert len(domains.ALL_SEEDS) == 38
    assert len(domains.ALL_SOURCES) == 62
