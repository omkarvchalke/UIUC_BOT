from app.ingestion.crawler import CrawlSeed
from app.models.conversation_session import StudentType

# One seed per approved domain -- deliberately domain-only, no
# path_prefixes scoping to a specific section: the point of this list is
# to *not* hand-curate which pages/sections matter (that was the previous
# approach, and it doesn't scale -- see the git history for how many
# individual URLs that took). Quality control instead happens per-page,
# inside Crawler itself: robots.txt, a login-wall check, a non-HTML/PDF
# check, a soft-404 check, a thinness floor, and a duplicate-content-hash
# check (see app/ingestion/crawler.py). max_depth and max_pages are the
# only per-seed levers; widen a seed's max_pages if a site turns out to
# have more real content than DEFAULT_MAX_PAGES reaches.
#
# Several of these domains (canvas, identity, answers, handshake, app) are
# expected to yield few or zero pages -- they're largely or entirely
# login-gated, and the crawler's login-wall check means it won't waste its
# page budget expanding past that wall. Seeding them anyway costs little
# and means a genuinely public page added to one of them later gets picked
# up automatically on the next crawl run, with no code change required.
DEFAULT_MAX_DEPTH = 4
DEFAULT_MAX_PAGES = 60

CRAWL_SEEDS: tuple[CrawlSeed, ...] = (
    CrawlSeed(
        start_url="https://admissions.illinois.edu",
        department="Undergraduate Admissions",
        max_depth=DEFAULT_MAX_DEPTH,
        max_pages=DEFAULT_MAX_PAGES,
    ),
    CrawlSeed(
        start_url="https://grad.illinois.edu",
        department="The Graduate College",
        default_student_types=(StudentType.GRADUATE,),
        max_depth=DEFAULT_MAX_DEPTH,
        max_pages=DEFAULT_MAX_PAGES,
    ),
    CrawlSeed(
        start_url="https://newstudent.illinois.edu",
        department="New Student & Family Experiences",
        default_student_types=(StudentType.FRESHMAN, StudentType.TRANSFER),
        max_depth=DEFAULT_MAX_DEPTH,
        max_pages=DEFAULT_MAX_PAGES,
    ),
    CrawlSeed(
        start_url="https://registrar.illinois.edu",
        department="Office of the Registrar",
        max_depth=DEFAULT_MAX_DEPTH,
        max_pages=DEFAULT_MAX_PAGES,
    ),
    CrawlSeed(
        start_url="https://courses.illinois.edu",
        department="Office of the Registrar",
        max_depth=DEFAULT_MAX_DEPTH,
        max_pages=DEFAULT_MAX_PAGES,
    ),
    CrawlSeed(
        start_url="https://catalog.illinois.edu",
        department="Office of the Provost",
        max_depth=DEFAULT_MAX_DEPTH,
        max_pages=DEFAULT_MAX_PAGES,
    ),
    CrawlSeed(
        start_url="https://isss.illinois.edu",
        department="International Student and Scholar Services",
        default_student_types=(StudentType.INTERNATIONAL,),
        max_depth=DEFAULT_MAX_DEPTH,
        max_pages=DEFAULT_MAX_PAGES,
    ),
    CrawlSeed(
        start_url="https://housing.illinois.edu",
        department="University Housing",
        max_depth=DEFAULT_MAX_DEPTH,
        max_pages=DEFAULT_MAX_PAGES,
    ),
    CrawlSeed(
        start_url="https://osfa.illinois.edu",
        department="Office of Student Financial Aid",
        max_depth=DEFAULT_MAX_DEPTH,
        max_pages=DEFAULT_MAX_PAGES,
    ),
    CrawlSeed(
        start_url="https://paymybill.uillinois.edu",
        department="University Bursar",
        max_depth=DEFAULT_MAX_DEPTH,
        max_pages=DEFAULT_MAX_PAGES,
    ),
    CrawlSeed(
        start_url="https://studentmoney.uillinois.edu",
        department="Student Money Management Center",
        max_depth=DEFAULT_MAX_DEPTH,
        max_pages=DEFAULT_MAX_PAGES,
    ),
    CrawlSeed(
        start_url="https://treasury.uillinois.edu",
        department="University Treasury",
        max_depth=DEFAULT_MAX_DEPTH,
        max_pages=DEFAULT_MAX_PAGES,
    ),
    CrawlSeed(
        start_url="https://icard.uillinois.edu",
        department="I-Card Office",
        max_depth=DEFAULT_MAX_DEPTH,
        max_pages=DEFAULT_MAX_PAGES,
    ),
    CrawlSeed(
        start_url="https://techservices.illinois.edu",
        department="Technology Services",
        max_depth=DEFAULT_MAX_DEPTH,
        max_pages=DEFAULT_MAX_PAGES,
    ),
    CrawlSeed(
        start_url="https://identity.uillinois.edu",
        department="Technology Services",
        max_depth=DEFAULT_MAX_DEPTH,
        max_pages=DEFAULT_MAX_PAGES,
    ),
    CrawlSeed(
        start_url="https://answers.uillinois.edu",
        department="Technology Services",
        max_depth=DEFAULT_MAX_DEPTH,
        max_pages=DEFAULT_MAX_PAGES,
    ),
    CrawlSeed(
        start_url="https://canvas.illinois.edu",
        department="Technology Services",
        max_depth=DEFAULT_MAX_DEPTH,
        max_pages=DEFAULT_MAX_PAGES,
    ),
    CrawlSeed(
        start_url="https://webstore.illinois.edu",
        department="University of Illinois Webstore",
        max_depth=DEFAULT_MAX_DEPTH,
        max_pages=DEFAULT_MAX_PAGES,
    ),
    CrawlSeed(
        # JS-rendered for anything dynamic (see README's Content coverage
        # section) -- kept anyway since static pages elsewhere on the site
        # (policies, service descriptions) may still have real content.
        start_url="https://library.illinois.edu",
        department="University Library",
        max_depth=DEFAULT_MAX_DEPTH,
        max_pages=DEFAULT_MAX_PAGES,
    ),
    CrawlSeed(
        start_url="https://careercenter.illinois.edu",
        department="The Career Center",
        max_depth=DEFAULT_MAX_DEPTH,
        max_pages=DEFAULT_MAX_PAGES,
    ),
    CrawlSeed(
        start_url="https://handshake.illinois.edu",
        department="The Career Center",
        max_depth=DEFAULT_MAX_DEPTH,
        max_pages=DEFAULT_MAX_PAGES,
    ),
    CrawlSeed(
        start_url="https://hireillini.illinois.edu",
        department="The Career Center",
        max_depth=DEFAULT_MAX_DEPTH,
        max_pages=DEFAULT_MAX_PAGES,
    ),
    CrawlSeed(
        start_url="https://campusrec.illinois.edu",
        department="Campus Recreation",
        max_depth=DEFAULT_MAX_DEPTH,
        max_pages=DEFAULT_MAX_PAGES,
    ),
    CrawlSeed(
        start_url="https://studentaffairs.illinois.edu",
        department="Student Affairs",
        max_depth=DEFAULT_MAX_DEPTH,
        max_pages=DEFAULT_MAX_PAGES,
    ),
    CrawlSeed(
        start_url="https://union.illinois.edu",
        department="Illini Union",
        max_depth=DEFAULT_MAX_DEPTH,
        max_pages=DEFAULT_MAX_PAGES,
    ),
    CrawlSeed(
        start_url="https://mckinley.illinois.edu",
        department="McKinley Health Center",
        max_depth=DEFAULT_MAX_DEPTH,
        max_pages=DEFAULT_MAX_PAGES,
    ),
    CrawlSeed(
        start_url="https://si.illinois.edu",
        department="Student Health Insurance",
        max_depth=DEFAULT_MAX_DEPTH,
        max_pages=DEFAULT_MAX_PAGES,
    ),
    CrawlSeed(
        start_url="https://counselingcenter.illinois.edu",
        department="Counseling Center",
        max_depth=DEFAULT_MAX_DEPTH,
        max_pages=DEFAULT_MAX_PAGES,
    ),
    CrawlSeed(
        start_url="https://parking.illinois.edu",
        department="Parking Department",
        max_depth=DEFAULT_MAX_DEPTH,
        max_pages=DEFAULT_MAX_PAGES,
    ),
    CrawlSeed(
        # Confirmed via an earlier crawl to be a client-side-rendered app
        # that serves the same static shell for every route -- kept in the
        # seed list per the approved-domains list, relying on Crawler's
        # duplicate-content-hash check to keep at most one copy of that
        # shell rather than hand-excluding the domain.
        start_url="https://map.illinois.edu",
        department="Facilities & Services",
        max_depth=DEFAULT_MAX_DEPTH,
        max_pages=DEFAULT_MAX_PAGES,
    ),
    CrawlSeed(
        start_url="https://police.illinois.edu",
        department="Division of Public Safety",
        max_depth=DEFAULT_MAX_DEPTH,
        max_pages=DEFAULT_MAX_PAGES,
    ),
    CrawlSeed(
        start_url="https://ready.illinois.edu",
        department="Emergency Management",
        max_depth=DEFAULT_MAX_DEPTH,
        max_pages=DEFAULT_MAX_PAGES,
    ),
    CrawlSeed(
        start_url="https://emergency.illinois.edu",
        department="Emergency Management",
        max_depth=DEFAULT_MAX_DEPTH,
        max_pages=DEFAULT_MAX_PAGES,
    ),
    CrawlSeed(
        start_url="https://commencement.illinois.edu",
        department="Office of the Registrar",
        max_depth=DEFAULT_MAX_DEPTH,
        max_pages=DEFAULT_MAX_PAGES,
    ),
    CrawlSeed(
        start_url="https://dres.illinois.edu",
        department="Disability Resources and Educational Services",
        max_depth=DEFAULT_MAX_DEPTH,
        max_pages=DEFAULT_MAX_PAGES,
    ),
    CrawlSeed(
        start_url="https://bookstore.illinois.edu",
        department="Illini Union Bookstore",
        max_depth=DEFAULT_MAX_DEPTH,
        max_pages=DEFAULT_MAX_PAGES,
    ),
    CrawlSeed(
        start_url="https://app.illinois.edu",
        department="Technology Services",
        max_depth=DEFAULT_MAX_DEPTH,
        max_pages=DEFAULT_MAX_PAGES,
    ),
    CrawlSeed(
        # Not an illinois.edu domain -- see the domain-safety allowlist in
        # tests/ingestion/test_sources.py. The actual authority for bus
        # fares/routes serving campus; illinois.edu has no equivalent.
        start_url="https://mtd.org",
        department="Champaign-Urbana Mass Transit District (MTD)",
        max_depth=DEFAULT_MAX_DEPTH,
        max_pages=DEFAULT_MAX_PAGES,
    ),
)
