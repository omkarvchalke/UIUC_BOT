"""Academics & Curriculum -- the course catalog and academic program
structure, via the Office of the Provost."""

from app.core.config import get_settings
from app.ingestion.crawl_seed import CrawlSeed
from app.ingestion.source_config import SourceConfig
from app.models.document import SourceType, Topic

_DEFAULT_MAX_DEPTH = get_settings().crawl_default_max_depth
_DEFAULT_MAX_PAGES = get_settings().crawl_default_max_pages

SEEDS: tuple[CrawlSeed, ...] = (
    CrawlSeed(
        start_url="https://catalog.illinois.edu",
        department="Office of the Provost",
        max_depth=_DEFAULT_MAX_DEPTH,
        max_pages=_DEFAULT_MAX_PAGES,
    ),
)

SOURCES: tuple[SourceConfig, ...] = (
    # CAMPUS_SERVICES_FACILITIES, not ACADEMICS: Source Manifest V2 classifies the whole
    # catalog.illinois.edu domain (per-department course listings, general degree/policy pages)
    # under Campus Services & Facilities, reserving ACADEMICS for Course Explorer/grades/GPA
    # content instead -- see the ambiguity noted on both topics' descriptions in
    # topic_classifier.py.
    SourceConfig(
        url="https://catalog.illinois.edu/",
        department="Office of the Provost",
        topic=Topic.CAMPUS_SERVICES_FACILITIES,
        source_type=SourceType.HTML,
        fallback_title="Course Catalog",
    ),
    # Same CAMPUS_SERVICES_FACILITIES reasoning as the catalog root above -- crawler-discovered
    # but landed under ADMISSIONS, dead-ending "How do I find out what gen-eds I still need?"
    # despite this being the actual gen-ed requirements page.
    SourceConfig(
        url="https://catalog.illinois.edu/general-information/degree-general-education-requirements",
        department="Office of the Provost",
        topic=Topic.CAMPUS_SERVICES_FACILITIES,
        source_type=SourceType.HTML,
        fallback_title="Degree and General Education Requirements",
    ),
    # A live run found "how do I contact my academic advisor" got zero
    # citations and was misclassified as academic_calendar -- UIUC advising
    # is decentralized per-college with no single university-wide advising
    # office, so this points at a real college's advising page as a
    # concrete example rather than a fabricated "central advising" page.
    # fallback_title names the college explicitly so the answer doesn't
    # imply it's university-wide. Originally pointed at the College of
    # LAS's advising page (the largest college by enrollment), but that
    # domain (las.illinois.edu, Pantheon-hosted) 403s this project's
    # ingestion client specifically -- confirmed the same URL returns 200
    # via curl with an identical User-Agent, so it's a WAF-level
    # TLS/HTTP-client fingerprint block, not a UA string check, and not
    # something worth engineering around. Grainger Engineering's advising
    # page is a real, fetchable substitute.
    SourceConfig(
        url="https://grainger.illinois.edu/academics/undergraduate/advising",
        department="The Grainger College of Engineering",
        topic=Topic.ACADEMIC_ADVISING,
        source_type=SourceType.HTML,
        fallback_title="Advising (The Grainger College of Engineering)",
    ),
    # Doesn't contradict the "no single university-wide advising office"
    # finding above -- this isn't an advising office, it's a campus-wide
    # "Student Success @ Illinois" navigation hub that explains *why*
    # advising is decentralized and links out to every college's own
    # advising site, plus genuinely general info (the Intercollegiate
    # Transfer process for changing majors, minors). Verified live (HTTP
    # 200, real substantive content) before adding.
    SourceConfig(
        url="https://studentsuccess.illinois.edu/student-resources/advising/",
        department="Student Success @ Illinois",
        topic=Topic.ACADEMIC_ADVISING,
        source_type=SourceType.HTML,
        fallback_title="Advising (Student Success @ Illinois)",
    ),
    # Closes a real content-coverage gap: a live audit found "What's the difference between a
    # major and a minor?" scoring below the rerank floor against every existing source. This page
    # directly explains what a minor is (credit-hour requirements, declaring one) in contrast to a
    # major -- same Grainger-advising-as-concrete-example reasoning as the source above (UIUC
    # advising is decentralized, no single university-wide "majors vs minors" page exists).
    SourceConfig(
        url="https://advising.grainger.illinois.edu/degree-programs/minors",
        department="The Grainger College of Engineering",
        topic=Topic.ACADEMIC_ADVISING,
        source_type=SourceType.HTML,
        fallback_title="Minors (The Grainger College of Engineering)",
    ),
)
