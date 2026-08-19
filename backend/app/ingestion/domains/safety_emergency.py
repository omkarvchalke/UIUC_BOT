"""Safety & Emergency -- campus policing, emergency preparedness, and
disability accommodations, via the Division of Public Safety, Emergency
Management, and Disability Resources and Educational Services (DRES)."""

from app.core.config import get_settings
from app.ingestion.crawl_seed import CrawlSeed
from app.ingestion.source_config import SourceConfig
from app.models.document import SourceType, Topic

_DEFAULT_MAX_DEPTH = get_settings().crawl_default_max_depth
_DEFAULT_MAX_PAGES = get_settings().crawl_default_max_pages

SEEDS: tuple[CrawlSeed, ...] = (
    CrawlSeed(
        start_url="https://police.illinois.edu",
        department="Division of Public Safety",
        max_depth=_DEFAULT_MAX_DEPTH,
        max_pages=_DEFAULT_MAX_PAGES,
    ),
    CrawlSeed(
        start_url="https://ready.illinois.edu",
        department="Emergency Management",
        max_depth=_DEFAULT_MAX_DEPTH,
        max_pages=_DEFAULT_MAX_PAGES,
    ),
    CrawlSeed(
        start_url="https://emergency.illinois.edu",
        department="Emergency Management",
        max_depth=_DEFAULT_MAX_DEPTH,
        max_pages=_DEFAULT_MAX_PAGES,
    ),
    CrawlSeed(
        start_url="https://dres.illinois.edu",
        department="Disability Resources and Educational Services",
        max_depth=_DEFAULT_MAX_DEPTH,
        max_pages=_DEFAULT_MAX_PAGES,
    ),
)

SOURCES: tuple[SourceConfig, ...] = (
    SourceConfig(
        # The root page's static text turned out thinner than it first
        # looked -- mostly nav links (SafeWalk, safety tips) plus rotating
        # news/crime-blotter snippets, no concrete phone numbers despite an
        # initial WebFetch summary suggesting otherwise (that summary
        # apparently drew on content this static scrape didn't actually
        # capture). The /contact/ subpage below has the real numbers;
        # keeping both since the root page's SafeWalk/mission content is
        # still real, just not the emergency-contact info a student most
        # likely wants.
        url="https://www.police.illinois.edu/",
        department="Division of Public Safety",
        topic=Topic.CAMPUS_SAFETY,
        source_type=SourceType.HTML,
        fallback_title="Division of Public Safety",
    ),
    SourceConfig(
        url="https://www.police.illinois.edu/contact/",
        department="Division of Public Safety",
        topic=Topic.CAMPUS_SAFETY,
        source_type=SourceType.HTML,
        fallback_title="Contact - Division of Public Safety",
    ),
    # Topic.ACCESSIBILITY_DISABILITY_SUPPORT didn't exist until a crawl of dres.illinois.edu
    # (added to the approved-domains crawler) surfaced the gap: with no
    # accessibility-specific topic to embed against, the classifier was
    # tagging DRES pages as international_student_services, which is a
    # hard retrieval filter -- see app/retrieval/topic_classifier.py.
    # Both URLs verified substantive (real numbered steps, not nav-only)
    # via the crawler's own extraction during that smoke test.
    SourceConfig(
        url="https://dres.illinois.edu/apply",
        department="Disability Resources and Educational Services",
        topic=Topic.ACCESSIBILITY_DISABILITY_SUPPORT,
        source_type=SourceType.HTML,
        fallback_title="Apply for Accommodations - DRES",
    ),
    SourceConfig(
        url="https://dres.illinois.edu/apply/documentation-requirements",
        department="Disability Resources and Educational Services",
        topic=Topic.ACCESSIBILITY_DISABILITY_SUPPORT,
        source_type=SourceType.HTML,
        fallback_title="Documentation Requirements - DRES",
    ),
    # Closes a real content-coverage gap: a live audit found "How do I request an interpreter for
    # a lecture?" scoring below the rerank floor against the two DRES sources above (apply/
    # documentation-requirements are about registering for accommodations generally, not
    # interpreting specifically).
    SourceConfig(
        url="https://dres.illinois.edu/accommodations/interpreting-and-live-captioning/",
        department="Disability Resources and Educational Services",
        topic=Topic.ACCESSIBILITY_DISABILITY_SUPPORT,
        source_type=SourceType.HTML,
        fallback_title="Interpreting and Live Captioning - DRES",
    ),
    # Closes a real content-coverage gap: a live audit found "What should I do if I lose my
    # wallet on campus?" scoring below the rerank floor -- the existing police.illinois.edu
    # sources cover general safety tips and contact info, not lost-and-found specifically.
    SourceConfig(
        url="https://police.illinois.edu/services/lost-and-found-property/",
        department="Division of Public Safety",
        topic=Topic.CAMPUS_SAFETY,
        source_type=SourceType.HTML,
        fallback_title="Lost and Found Property",
    ),
    # Closes a real content-coverage gap: a live audit found "What's the process for a welfare
    # check on a friend?" scoring below the rerank floor -- no existing source covers this at
    # all. The Office of the Dean of Students' Community of Care referral is the actual UIUC
    # process for reporting a concern about another student's wellbeing (not a police report
    # unless there's an immediate emergency, which this page itself explains). Not a full crawl
    # seed for odos.illinois.edu -- this is the one page a content-coverage audit specifically
    # found missing, same "one targeted page, not a whole-domain crawl" pattern as the career_
    # employment.py/graduation_records.py additions from the same audit.
    SourceConfig(
        url="https://odos.illinois.edu/community-of-care/referral",
        department="Office of the Dean of Students",
        topic=Topic.CAMPUS_SAFETY,
        source_type=SourceType.HTML,
        fallback_title="Refer a Student - Community of Care",
    ),
)
