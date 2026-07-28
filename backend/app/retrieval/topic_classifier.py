import math
from dataclasses import dataclass
from functools import lru_cache

from app.embeddings.embedder import Embedder
from app.models.document import Topic

# Short natural-language description of each topic, embedded once and
# compared against the user's message via cosine similarity. Chosen over
# keyword matching (brittle, misses paraphrases) and over an extra LLM call
# per message (an added network round-trip and cost for every turn) as a
# middle ground that's deterministic, CPU-only, and reuses the embedding
# infrastructure already built in Phase 4.
#
# Used only to decide whether to ask a clarifying question -- NOT as a
# retrieval filter (see nodes.make_retrieve_node): "How do I apply for OPT?"
# classified as "admissions" at 0.65 confidence (above the clarification
# threshold) purely from "apply"/"application" overlapping with the
# admissions description below, while hybrid search with no topic filter
# ranked the real OPT page #1. A wrong classification here just means an
# occasional unnecessary clarifying question; as a hard filter it would
# have silently returned zero results instead.
_TOPIC_DESCRIPTIONS: dict[Topic, str] = {
    # "letters of recommendation" added in a 39-xfail follow-up round (see
    # the REGISTRATION-attractor comment below for the regression suite
    # this refers to): "Do I need letters of recommendation to apply?" was
    # losing to Topic.REGISTRATION with nothing recommendation-specific to
    # compete with it. Several other candidate additions to this
    # description (early action/regular decision, deferring admission,
    # declaring a major) were tried and rejected in the same round --
    # each caused new regressions on "How do I apply for financial aid?"
    # or similar, since ADMISSIONS' "apply"/"new student" wording is
    # already a near-default match for anything application-shaped.
    Topic.ADMISSIONS: (
        "becoming a new UIUC student: freshman or transfer admission requirements, "
        "essays, letters of recommendation, deadlines for prospective and "
        "incoming students"
    ),
    # Was just "registering as a new or continuing student" -- short enough
    # that it acted as a generic default attractor for almost anything
    # administrative-sounding ("sign up", "register with", "apply for", "a
    # hold on my account"), the single biggest source of misclassifications
    # found by the 306-case regression suite (app/evaluation/
    # topic_regression_set.py): 15 of its 63 xfail cases specifically lost
    # to Topic.REGISTRATION, spanning 9 different *other* correct topics.
    #
    # Rewritten to (a) explicitly name New Student Registration (NSR) as
    # the specific first-time-enrollment event this topic is really about
    # -- not generic "registering" -- and (b) add the *other* real content
    # actually filed under this topic (Office of the Registrar records:
    # transcripts, FERPA, diplomas, leaving the university, enrollment
    # verification letters), which had no representation in the
    # description at all despite being real, explicitly-sourced content
    # (see app/ingestion/domains/registration_records.py).
    #
    # This traded 8 fixed misclassifications for 1 new one ("Can I skip New
    # Student Registration if I've already registered for classes?", a
    # compound query that names both senses of "register" in one sentence
    # -- accepted as a residual, see topic_regression_set.py) -- verified
    # against the full 306-case regression suite, not just the queries
    # motivating the change. Also revealed 3 cases originally assumed to be
    # about NSR ("When can continuing students register for classes?",
    # "How do I check my registration appointment time?", "Do continuing
    # students need to register every semester?") that, on reflection, are
    # genuinely more about course registration mechanics than the one-time
    # NSR event -- relabeled to Topic.COURSE_REGISTRATION in the regression
    # suite rather than fought for here.
    Topic.REGISTRATION: (
        "New Student Registration (NSR), completing registration as a new "
        "or continuing student before your first semester, plus other "
        "Office of the Registrar records services: enrollment "
        "verification letters, transcripts, FERPA privacy, diplomas, and "
        "leaving the university"
    ),
    Topic.ORIENTATION: "new student orientation, welcome week, orientation programs",
    # Was "on-campus housing..." -- the REGISTRATION-attractor follow-up
    # round (306-case regression suite) found "on-campus" was itself acting
    # as a mini-attractor: 5 unrelated queries mentioning "on campus"
    # (international student resources, printing documents, reserving a
    # library study room, campus pools, working on campus) were losing to
    # Topic.HOUSING purely off that bigram. Swapping to "student housing"
    # (same meaning, no shared "on campus" wording with the retrieval
    # corpus's other "on campus X" phrasing) fixed all 5 with zero
    # regressions -- verified against the full 306-case suite. "move-in
    # day" and "dorm room types" added on top of that fix, for "single-
    # occupancy dorm rooms" and "earliest move-in" queries that scored
    # below threshold without them.
    Topic.HOUSING: (
        "student housing, residence halls, dorms, where students live, "
        "move-in day, and dorm room types"
    ),
    Topic.DINING: "dining halls, meal plans, food on campus",
    # "Illinois Commitment" and "i-card banking services" deliberately in
    # the description text -- two separate real findings from the same
    # 200-question sweep: "What is the Illinois Commitment program?" scored
    # 0.436 (below threshold, not even top-ranked) without the program name;
    # "What banking options are available through the i-card?" scored
    # closest to Topic.VISA (0.569 vs financial_aid's 0.564, an unrelated
    # near-tie -- "i-card" has no strong single-topic home in this
    # taxonomy) without the i-card phrase, misclassifying to visa and
    # answering with U-visa/TRUST-Act content for a banking question.
    # "billing refunds and overpayments" deliberately added too: "Are there
    # refund options for overpayment?" scored 0.519 (below financial_aid's
    # closest competitor, health_insurance's "waiving/opting out" phrasing
    # below) without it.
    # "buying textbooks" deliberately added too: a re-test-all-cases sweep
    # found "Where do I buy textbooks?" had regressed to Topic.REGISTRATION
    # (0.572 vs financial_aid's 0.564) after other topics' descriptions
    # below got more specific and narrowed their generic footprint,
    # leaving registration's short, generic description ("registering as a
    # new or continuing student") an unintended default attractor for
    # administrative-sounding queries it has nothing to do with.
    Topic.FINANCIAL_AID: (
        "financial aid, tuition costs, paying for college, FAFSA, "
        "the Illinois Commitment free-tuition program, i-card banking services, "
        "billing refunds and overpayments, buying textbooks"
    ),
    # "scholarship application deadlines" added in a 39-xfail follow-up
    # round: "What is the deadline to apply for scholarships?" was losing
    # to Topic.ACADEMIC_CALENDAR, whose bare "deadlines" wording is a
    # recurring attractor across several topics.
    Topic.SCHOLARSHIPS: (
        "scholarships and merit awards, including scholarship application deadlines"
    ),
    # "Hire Illini" (the job board's actual name) deliberately in the
    # description text -- same bare-proper-noun pattern as Illinois
    # Commitment above: 0.558 without it, below threshold.
    # "work hour limits" deliberately added too: same Topic.REGISTRATION
    # attractor problem as financial_aid's "buying textbooks" above --
    # "How many hours can I work as a student employee?" had regressed to
    # registration (0.635 vs student_employment's 0.620).
    # "graduate assistantships" added in the REGISTRATION-attractor follow-up
    # round: "What's the difference between a graduate assistantship and
    # work study?" was losing to Topic.OPT with no assistantship wording to
    # compete with. "applying for" prefixed onto it in a later 39-xfail
    # follow-up round: "How do I apply for a graduate assistantship?" was
    # separately losing to Topic.ACADEMIC_ADVISING until this was added.
    Topic.STUDENT_EMPLOYMENT: (
        "on-campus jobs, work study, student employment, applying for "
        "graduate assistantships, Hire Illini job board, work hour limits"
    ),
    # "ISSS" spelled out deliberately in the description text -- same
    # bare-acronym pattern as OPT above: 0.572 without it, below threshold.
    # "pre-arrival preparation and check-in" added in the
    # REGISTRATION-attractor follow-up round: "What should international
    # students do before they arrive on campus?" was losing to
    # Topic.ADMISSIONS, which shares "new"/"incoming student" wording.
    # "campus resources specifically for international students" added in
    # a later 39-xfail follow-up round: "What resources are available for
    # international students on campus?" was separately losing to
    # Topic.HOUSING/DINING purely off the generic "on campus" phrase.
    Topic.INTERNATIONAL_STUDENT_SERVICES: (
        "international student services and support, "
        "ISSS (International Student and Scholar Services), pre-arrival "
        "preparation and check-in, and campus resources specifically for "
        "international students"
    ),
    # "SEVIS" added in the REGISTRATION-attractor follow-up round: "What is
    # SEVIS and why does it matter?" scored 0.487, below the clarification
    # threshold, with no SEVIS-specific wording anywhere in the taxonomy.
    Topic.VISA: (
        "visa status, I-20, SEVIS (Student and Exchange Visitor "
        "Information System) record, immigration documents"
    ),
    Topic.CPT: "curricular practical training, CPT work authorization",
    # "what is OPT" is deliberately in the description text, not just
    # "optional practical training": bare acronym questions like "What is
    # OPT?" scored 0.50 (below the 0.55 threshold) without it, incorrectly
    # triggering an ambiguous-topic clarification instead of answering --
    # found via the golden-set eval (app/evaluation/golden_set.py).
    Topic.OPT: "what is OPT, optional practical training, OPT work authorization after graduation",
    Topic.TECHNOLOGY_SERVICES: "campus technology, wifi, email, IT help desk",
    # "study room reservations" added in a 39-xfail follow-up round: "Can I
    # reserve a study room in the library?" was losing to Topic.HOUSING
    # purely off generic wording, with nothing study-room-specific to
    # compete with it. An earlier wording ("reserving a study room")
    # regressed "Where do I buy textbooks?" and "How do I reset my
    # university password?" by pulling too much weight toward LIBRARIES;
    # this phrasing didn't.
    Topic.LIBRARIES: "university library hours, services, locations, and study room reservations",
    # Built up incrementally from real sweep failures, each phrase added
    # for a specific query that scored below its competitor without it:
    # "MTD bus passes/fares" (bare-acronym pattern, same as OPT/ISSS above)
    # for "How much does an MTD bus pass cost?"; "permit renewals, tickets
    # and appeals" and "real-time bus tracking" for "How do I renew my
    # parking permit?" / "...appeal a parking ticket?" / "...track the
    # campus bus in real time?", all of which had regressed to
    # Topic.REGISTRATION or Topic.CAMPUS_SAFETY once other topics'
    # descriptions elsewhere got more specific and stopped acting as
    # generic attractors themselves.
    #
    # That version (a comma-separated list of narrow parking/bus phrases
    # plus a bare "Willard Airport") then regressed on a *retest* sweep: 5
    # airport/intercity-travel queries that previously classified correctly
    # ("...O'Hare Airport to UIUC...", "...cheapest way...from Chicago?",
    # "...parking rates on campus?", "...shuttle to the airport?",
    # "...Midway Airport to campus?") started losing to
    # Topic.ADMISSIONS/DINING/HOUSING instead. Root cause: the added
    # parking/ticket/bus-tracking phrases were specific enough to dominate
    # the embedding, diluting the airport/intercity-travel signal down to a
    # single under-weighted proper noun.
    #
    # Fixed by rewriting as one coherent sentence ("getting around campus
    # and to/from campus: ...") instead of a growing list of bolted-on
    # phrases, and naming Chicago/O'Hare/Midway explicitly instead of
    # relying on "Willard Airport" alone to imply intercity travel. Verified
    # via a comprehensive check across all 23 queries accumulated from every
    # fix made this session (not just the 5 that regressed): 0 failures,
    # including "Does UIUC have its own airport?" which a previous version
    # of this description could never pass at the same time as the
    # permit/ticket/bus-tracking queries.
    # "whether you need a car as a student" and "campus bike share" added in
    # the REGISTRATION-attractor follow-up round: "Do I need a car as a
    # UIUC student?" and "Does UIUC have a bike share program?" were both
    # losing to Topic.ADMISSIONS purely off "as a ... student"/"UIUC"
    # wording, with nothing car- or bike-specific to compete with it.
    Topic.TRANSPORTATION: (
        "getting around campus and to/from campus: parking permits and tickets, "
        "MTD buses, whether you need a car as a student, campus bike share, "
        "Willard Airport, and traveling from Chicago or O'Hare/Midway airports"
    ),
    # "waiving or opting out" deliberately in the description text: a real
    # 200-question sweep found "Can I opt out of the mandatory health
    # insurance?" misclassified as Topic.OPT (0.644 vs 0.637, a near-tie)
    # purely from "opt" surface-overlapping OPT's description, retrieving a
    # completely unrelated MTD privacy-policy chunk. Re-verified this
    # description change alone fixes the near-tie (0.82 vs 0.64) without
    # weakening real OPT queries ("How do I apply for OPT?" stays 0.70 vs
    # 0.59).
    # "seeing a doctor... McKinley Health Center" deliberately added too:
    # raised "Where do I go for a doctor's appointment on campus?" from
    # 0.533 to 0.643, though not quite enough -- Topic.DINING wins that
    # specific query at 0.650 for reasons unrelated to either description
    # (no dining-specific wording in the query at all). Left as a real,
    # documented residual limitation rather than chasing a third
    # competitor's description -- see docs/production-readiness.md-style
    # honesty: this genuinely helps grounding for other doctor/McKinley
    # phrasings even though it didn't flip this exact one.
    # "for both undergraduate and graduate students" and "flu shots" added in
    # the REGISTRATION-attractor follow-up round: "Does UIUC offer graduate
    # student health insurance?" was losing to Topic.ADMISSIONS (which
    # mentions "graduate" admission), and "Where can I get a flu shot on
    # campus?" was losing to Topic.DINING on generic "on campus" wording.
    Topic.HEALTH_INSURANCE: (
        "student health insurance and health services for both "
        "undergraduate and graduate students, waiving or opting out of the "
        "mandatory health insurance plan, seeing a doctor, flu shots, or "
        "medical appointments at McKinley Health Center"
    ),
    # "intramural sports" and "the climbing wall" added in the
    # REGISTRATION-attractor follow-up round: both were losing to
    # Topic.STUDENT_ORGANIZATIONS (registered clubs), a related but
    # distinct concept, with nothing recreation-specific to compete with it.
    # Bare "pool" added right after "gym" in a later 39-xfail follow-up
    # round: "Does the campus have a swimming pool?" was losing to
    # Topic.HOUSING. Longer phrasings ("an indoor swimming pool") were
    # tried first and rejected -- they diluted the description enough to
    # cost "Can I rent kayaks...from the rec center?" to Topic.TRANSPORTATION
    # instead; the single bare word didn't.
    Topic.CAMPUS_RECREATION: (
        "gym, pool, fitness facilities, recreation center membership, "
        "intramural sports, and the climbing wall"
    ),
    Topic.STUDENT_ORGANIZATIONS: "student clubs and registered student organizations",
    # "winter break dates" added in a 39-xfail follow-up round: "When does
    # winter break start and end?" scored 0.541, just below the
    # clarification threshold. A plain "winter break" (no "dates" suffix)
    # regressed two Dining Dollars/semester-rollover questions to
    # Topic.ACADEMIC_CALENDAR instead.
    Topic.ACADEMIC_CALENDAR: (
        "the academic calendar, semester dates, winter break dates, and add/drop deadlines"
    ),
    Topic.COURSE_REGISTRATION: "registering for classes, course registration",
    # "Illini-Alert emergency notifications" added in the
    # REGISTRATION-attractor follow-up round: "How do I sign up for
    # Illini-Alert emergency notifications?" was losing to
    # Topic.STUDENT_EMPLOYMENT purely off "sign up" wording, with no
    # Illini-Alert-specific phrase to compete with it.
    Topic.CAMPUS_SAFETY: (
        "campus police, emergency contacts, Illini-Alert emergency "
        "notifications, safety escorts, and crime reporting"
    ),
    # Added after the domain-only crawler (app/ingestion/crawl_seeds.py) hit
    # dres.illinois.edu (Disability Resources and Educational Services) and,
    # with no accessibility-specific topic to embed against, misclassified
    # most of its pages as international_student_services -- confirmed via a
    # live crawl smoke test. topic is a hard retrieval filter
    # (VectorRepository._build_filter), so a wrong topic here doesn't just
    # mislabel a page, it hides it from accessibility queries entirely and
    # pollutes results for whatever topic it got misclassified into.
    # "registering with DRES" added in a 39-xfail follow-up round: "Do I
    # need a doctor's note to register with DRES?" was losing to
    # Topic.REGISTRATION purely off the word "register" -- despite the
    # irony of adding register-adjacent wording to fix a REGISTRATION-
    # attractor case, this fixed it cleanly with zero regressions
    # (verified against the full 306-case suite) and, as a bonus, also
    # fixed "Do libraries offer virtual reality resources?" which had been
    # losing to this topic's old, more generic wording.
    Topic.ACCESSIBILITY: (
        "disability accommodations, accessibility services, registering "
        "with DRES, note-taking and testing accommodations for students "
        "with disabilities"
    ),
    # Added after a live run found "what career services does UIUC offer"
    # misclassified as international_student_services -- with no
    # career-specific description to embed against, "career" pulled toward
    # whichever topic happened to be closest. Deliberately distinguished
    # from STUDENT_EMPLOYMENT (on-campus jobs/work-study) since "career
    # coaching" and "resume review" are a different service from "I need a
    # job on campus," even though both live under The Career Center.
    #
    # Rewritten in the REGISTRATION-attractor follow-up round: the original
    # wording still lost the bare query "What career services does UIUC
    # offer?" to Topic.ADMISSIONS (a nearly identical phrasing with "like
    # resume help" appended passed, showing the classification was fragile
    # to small wording changes). Restructured to lead with "career services
    # offered by the Career Center" as one coherent clause instead of a
    # comma-list starting with the bare, generic word "career" -- fixed
    # with zero regressions against the full 306-case suite.
    Topic.CAREER_SERVICES: (
        "career services offered by the Career Center: resume and cover "
        "letter review, interview prep, career coaching, and job and "
        "internship search help"
    ),
    # Added after a live run found "how do I contact my academic advisor"
    # misclassified as academic_calendar -- same root cause as
    # CAREER_SERVICES above, no dedicated topic to embed against.
    Topic.ACADEMIC_ADVISING: (
        "academic advising, contacting or scheduling with your academic advisor, "
        "degree planning, course selection help"
    ),
}


@dataclass(frozen=True)
class TopicClassification:
    topic: Topic | None
    confidence: float


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    return dot / (norm_a * norm_b)


@lru_cache
def _topic_embeddings() -> dict[Topic, list[float]]:
    embedder = Embedder()
    topics = list(_TOPIC_DESCRIPTIONS)
    vectors = embedder.embed_documents([_TOPIC_DESCRIPTIONS[topic] for topic in topics])
    return dict(zip(topics, vectors, strict=True))


class TopicClassifier:
    """Classifies a message into a Topic by embedding similarity, with a
    confidence score the caller uses to decide whether to trust it or ask
    for clarification instead of guessing."""

    def __init__(
        self, *, confidence_threshold: float = 0.55, embedder: Embedder | None = None
    ) -> None:
        self._threshold = confidence_threshold
        self._embedder = embedder or Embedder()

    def classify(self, message: str) -> TopicClassification:
        query_vector = self._embedder.embed_query(message)
        topic_vectors = _topic_embeddings()

        best_topic: Topic | None = None
        best_score = -1.0
        for topic, vector in topic_vectors.items():
            score = _cosine(query_vector, vector)
            if score > best_score:
                best_topic, best_score = topic, score

        if best_score < self._threshold:
            return TopicClassification(topic=None, confidence=best_score)
        return TopicClassification(topic=best_topic, confidence=best_score)
