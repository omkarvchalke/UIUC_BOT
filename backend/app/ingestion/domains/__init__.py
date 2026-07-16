"""Knowledge Domain modules -- one file per approved UIUC Knowledge Domain,
each exporting its own `SEEDS` (and, where applicable, `SOURCES`) slice.
This package aggregates all of them into the two flat tuples the rest of
the ingestion pipeline reads from.
"""

from app.ingestion.crawl_seed import CrawlSeed
from app.ingestion.domains import (
    academics_curriculum,
    admissions_enrollment,
    career_employment,
    financial_aid_billing,
    graduation_records,
    housing_dining,
    international_services,
    libraries_research,
    recreation_wellness,
    registration_records,
    safety_emergency,
    student_life,
    technology_services,
    transportation_access,
)
from app.ingestion.source_config import SourceConfig

_MODULES = (
    admissions_enrollment,
    registration_records,
    academics_curriculum,
    financial_aid_billing,
    housing_dining,
    student_life,
    recreation_wellness,
    international_services,
    career_employment,
    technology_services,
    libraries_research,
    safety_emergency,
    transportation_access,
    graduation_records,
)

ALL_SEEDS: tuple[CrawlSeed, ...] = tuple(seed for module in _MODULES for seed in module.SEEDS)
ALL_SOURCES: tuple[SourceConfig, ...] = tuple(
    source for module in _MODULES for source in module.SOURCES
)
