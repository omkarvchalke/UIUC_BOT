from app.ingestion.crawler import CrawlSeed
from app.models.conversation_session import StudentType

# One seed per domain already represented in sources.py, bounded to the
# site section that's actually relevant to student onboarding --
# path_prefixes deliberately excludes news, staff directories, research
# pages, and other sections a full-site crawl would otherwise pull in.
# max_depth/max_pages are a starting point, not a tuned ceiling; widen them
# per-seed if a section turns out to have more useful pages than it
# currently allows for.
CRAWL_SEEDS: tuple[CrawlSeed, ...] = (
    CrawlSeed(
        start_url="https://www.admissions.illinois.edu/apply",
        department="Undergraduate Admissions",
        path_prefixes=("/apply",),
        # Deliberately no default_student_types: this section covers
        # freshman, transfer, and international applicants under different
        # subpaths, so per-page URL/title keyword inference
        # (crawler._infer_student_types) does the real work here.
    ),
    CrawlSeed(
        start_url="https://grad.illinois.edu/admissions",
        department="The Graduate College",
        path_prefixes=("/admissions",),
        default_student_types=(StudentType.GRADUATE,),
    ),
    CrawlSeed(
        start_url="https://housing.illinois.edu/living-communities",
        department="University Housing",
        path_prefixes=("/living-communities", "/dine"),
    ),
    CrawlSeed(
        start_url="https://isss.illinois.edu/students",
        department="International Student and Scholar Services",
        path_prefixes=("/students",),
        default_student_types=(StudentType.INTERNATIONAL,),
    ),
    CrawlSeed(
        start_url="https://mckinley.illinois.edu",
        department="McKinley Health Center",
        path_prefixes=("/fees", "/services"),
    ),
    CrawlSeed(
        start_url="https://newstudent.illinois.edu/orientation",
        department="New Student & Family Experiences",
        path_prefixes=("/orientation",),
        default_student_types=(StudentType.FRESHMAN, StudentType.TRANSFER),
    ),
    CrawlSeed(
        start_url="https://parking.illinois.edu",
        department="Parking Department",
        max_pages=15,
    ),
    CrawlSeed(
        start_url="https://registrar.illinois.edu/registration",
        department="Office of the Registrar",
        path_prefixes=("/registration",),
    ),
    CrawlSeed(
        start_url="https://studentengagement.illinois.edu/soda",
        department="Student Engagement",
        path_prefixes=("/soda",),
    ),
    CrawlSeed(
        start_url="https://www.osfa.illinois.edu/types-of-aid",
        department="Office of Student Financial Aid",
        path_prefixes=("/types-of-aid",),
    ),
    CrawlSeed(
        start_url="https://www.techservices.illinois.edu",
        department="Technology Services",
        max_pages=15,
    ),
    CrawlSeed(
        start_url="https://campusrec.illinois.edu",
        department="Campus Recreation",
        max_pages=15,
    ),
    CrawlSeed(
        # library.illinois.edu is JS-rendered for anything dynamic (see
        # README's Content coverage section) -- included anyway since
        # static pages elsewhere on the site (policies, service
        # descriptions) may still have real content, just capped low since
        # it's the least likely seed to pay off.
        start_url="https://www.library.illinois.edu",
        department="University Library",
        max_pages=10,
    ),
)
