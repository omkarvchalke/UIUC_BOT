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
#
# MIGRATED to Source Manifest V2's 21-topic taxonomy (see
# backend/scripts/data/source_manifest_v2.md and app/models/document.py's
# Topic docstring). Wording below is deliberately carried over/merged from
# the previous 24-topic taxonomy's descriptions wherever a new topic maps
# cleanly onto one or more old ones, rather than rewritten from scratch --
# every phrase kept here was independently earned by a real regression-set
# or live-sweep failure (see app/evaluation/topic_regression_set.py's module
# docstring for that history) and there is no equivalent verified history
# yet for brand-new wording. Two genuinely new topics with no direct old
# equivalent (ACADEMICS, CAMPUS_SERVICES_FACILITIES) are grounded directly
# in what Source Manifest V2 actually lists under each -- see the comments
# on those two entries for the specific ambiguity between them.
_TOPIC_DESCRIPTIONS: dict[Topic, str] = {
    Topic.ADMISSIONS: (
        "becoming a new UIUC student: freshman or transfer admission requirements, "
        "essays, letters of recommendation, deadlines for prospective and "
        "incoming students"
    ),
    Topic.REGISTRATION_RECORDS: (
        "New Student Registration (NSR), completing registration as a new "
        "or continuing student before your first semester, registering for "
        "classes and course registration, plus other Office of the "
        "Registrar records services: enrollment verification letters, "
        "transcripts, FERPA privacy, diplomas, and leaving the university"
    ),
    Topic.ORIENTATION_NEW_STUDENTS: "new student orientation, welcome week, orientation programs",
    Topic.HOUSING: (
        "student housing, residence halls, dorms, where students live, "
        "move-in day, and dorm room types"
    ),
    Topic.DINING: "dining halls, meal plans, food on campus",
    # "billing refunds and overpayments" deliberately moved OUT of this description and into
    # FINANCIAL_AID_COSTS below -- Source Manifest V2 splits registrar tuition/fee/billing pages
    # (a small, narrow topic: 9 documents) from general financial-aid/scholarship content (73
    # documents) that this topic now covers. "buying textbooks" also moved out, to
    # CAMPUS_SERVICES_FACILITIES below -- V2's per-URL data places the actual bookstore pages
    # there, not here (see app/ingestion/domains/graduation_records.py for the full reasoning);
    # "i-card banking services" stays since that's a genuinely separate concept from the i-card
    # *services* content CAMPUS_SERVICES_FACILITIES covers (getting/using the physical ID card
    # vs. its optional banking/debit feature).
    Topic.FINANCIAL_AID_SCHOLARSHIPS: (
        "financial aid, tuition costs, paying for college, FAFSA, "
        "the Illinois Commitment free-tuition program, i-card banking services, "
        "scholarships and merit awards, including scholarship application deadlines"
    ),
    # NEW, narrow topic (Source Manifest V2 lists only 9 documents under it): registrar
    # billing/fee pages specifically, split out of the old FINANCIAL_AID description above so a
    # broad "how do I pay for college" query still lands on FINANCIAL_AID_SCHOLARSHIPS (the much
    # more common ask) while a specific billing/refund query has somewhere precise to go.
    Topic.FINANCIAL_AID_COSTS: (
        "tuition and fee rates, registrar billing, refunds of registration "
        "charges, tuition waivers and fee exemptions, and withdrawal refund policies"
    ),
    Topic.CAREER_EMPLOYMENT: (
        "career services offered by the Career Center: resume and cover "
        "letter review, interview prep, career coaching, and job and "
        "internship search help, plus on-campus jobs, work study, student "
        "employment, applying for graduate assistantships, Hire Illini job "
        "board, and work hour limits"
    ),
    Topic.INTERNATIONAL_STUDENTS_IMMIGRATION: (
        "international student services and support, ISSS (International "
        "Student and Scholar Services), pre-arrival preparation and "
        "check-in, campus resources specifically for international "
        "students, visa status, I-20, SEVIS (Student and Exchange Visitor "
        "Information System) record, immigration documents, curricular "
        "practical training (CPT) work authorization, what is CPT, and "
        "optional practical training (OPT) work authorization after "
        "graduation, what is OPT"
    ),
    Topic.TECHNOLOGY_SERVICES: "campus technology, wifi, email, IT help desk",
    Topic.LIBRARIES: "university library hours, services, locations, and study room reservations",
    Topic.TRANSPORTATION_PARKING: (
        "getting around campus and to/from campus: parking permits and tickets, "
        "MTD buses, whether you need a car as a student, campus bike share, "
        "Willard Airport, and traveling from Chicago or O'Hare/Midway airports"
    ),
    # "counseling and mental health support" added on the HEALTH_INSURANCE -> HEALTH_WELLNESS
    # rename: Source Manifest V2's Health & Wellness topic (97 documents, up from 92 under the
    # old, narrower Health Insurance topic) explicitly includes Counseling Center content that
    # had no representation in the description before.
    Topic.HEALTH_WELLNESS: (
        "student health insurance and health services for both "
        "undergraduate and graduate students, waiving or opting out of the "
        "mandatory health insurance plan, seeing a doctor, flu shots, "
        "medical appointments at McKinley Health Center, and counseling "
        "and mental health support"
    ),
    Topic.CAMPUS_RECREATION: (
        "gym, pool, fitness facilities, recreation center membership, "
        "intramural sports, and the climbing wall"
    ),
    Topic.STUDENT_ORGANIZATIONS_ENGAGEMENT: "student clubs and registered student organizations",
    Topic.ACADEMIC_CALENDAR_GRADUATION: (
        "the academic calendar, semester dates, winter break dates, and "
        "add/drop deadlines, plus graduation and commencement: ceremony "
        "schedules, caps and gowns, diplomas, and conferral dates"
    ),
    # NEW topic. Source Manifest V2 splits what the old COURSE_REGISTRATION topic covered into
    # two: this one (registrar-side course/grade mechanics -- Course Explorer, GPA, grades,
    # auditing, general education requirements, Graduate College general info) and
    # CAMPUS_SERVICES_FACILITIES below (the actual per-department course catalog listings).
    # Genuinely ambiguous case, flagged rather than hidden: a query like "what classes does the
    # History department offer" could plausibly land on either topic -- this is a real,
    # unresolved edge documented here rather than claimed away, same honesty convention as the
    # residual limitations noted elsewhere in this file.
    Topic.ACADEMICS: (
        "checking your grades, calculating your GPA, auditing a course, "
        "general education requirements by category, using Course "
        "Explorer to browse class schedules and sections, and general "
        "information about the Graduate College"
    ),
    Topic.CAMPUS_SAFETY: (
        "campus police, emergency contacts, Illini-Alert emergency "
        "notifications, safety escorts, and crime reporting"
    ),
    Topic.ACCESSIBILITY_DISABILITY_SUPPORT: (
        "disability accommodations, accessibility services, registering "
        "with DRES, note-taking and testing accommodations for students "
        "with disabilities"
    ),
    # NEW topic. Source Manifest V2 groups two previously separate kinds of content here: (a)
    # per-department course catalog listings (e.g. "AE - Aerospace Engineering" course
    # descriptions) -- distinct from ACADEMICS' Course Explorer/grades content above, see that
    # entry's comment -- and (b) Illini Union / campus bookstore / i-card / campus map pages,
    # which the previous taxonomy had no dedicated home for and which a known corpus-hygiene
    # issue (see project memory) had leaking into ADMISSIONS instead.
    Topic.CAMPUS_SERVICES_FACILITIES: (
        "course descriptions and offerings by academic department or "
        "subject in the course catalog, general degree and curriculum "
        "policy information, and campus facilities and services: the "
        "Illini Union building, buying textbooks and the campus bookstore, "
        "i-card student ID services, and campus maps"
    ),
    Topic.ACADEMIC_ADVISING: (
        "academic advising, contacting or scheduling with your academic advisor, "
        "degree planning, course selection help"
    ),
}

# Additional short, narrow exemplar phrases for topics whose single
# _TOPIC_DESCRIPTIONS entry can't be tuned any further without regressing
# something else -- confirmed live via the (pre-migration) 306-case
# regression suite for ADMISSIONS, ACADEMIC_CALENDAR_GRADUATION,
# FINANCIAL_AID_SCHOLARSHIPS, and REGISTRATION_RECORDS/ACADEMICS (formerly
# COURSE_REGISTRATION), each of which resisted every wording-level fix
# attempted across three separate rounds under the old taxonomy (see
# topic_regression_set.py's module docstring). Carried over and remapped to
# the new topic keys.
#
# A topic's match score is the MAX cosine similarity across its primary
# description (above) plus all of its exemplars here, not their average or
# a re-embedded concatenation -- so an exemplar added for one narrow query
# can't dilute the primary description's match strength for that topic's
# other, already-passing queries the way editing the description text
# directly always risked.
_TOPIC_EXEMPLARS: dict[Topic, tuple[str, ...]] = {
    Topic.FINANCIAL_AID_SCHOLARSHIPS: (
        "when is the FAFSA due each year",
        "using the net price calculator to estimate cost",
        "what is a federal Pell Grant",
        "tuition waivers that cover part of your tuition bill",
        "merit awards available to first-year students right out of high school",
        "automatic merit scholarships freshmen receive upon admission",
        "merit awards set aside specifically for transfer students",
        # Regressed once this topic's exemplar list above (already a merge of the old
        # FINANCIAL_AID and SCHOLARSHIPS topics) had to compete against several other topics'
        # newly-merged, longer descriptions too -- same dilution pattern as elsewhere in this
        # migration.
        "checking the current status of your financial aid award",
        "whether international students are eligible for any financial aid",
        "the deadline to submit a scholarship application",
    ),
    Topic.HOUSING: (
        "packing and moving into your dorm room for the first time",
        "single-occupancy dorm rooms and the extra fee for a private room",
        "getting released from your dorm residency agreement",
    ),
    # No exemplars existed for either topic below before -- both relied solely on their plain
    # descriptions. Confirmed live (150-question sweep): every query below landed on a wrong topic
    # confident and thin-relaxation-proof enough to dead-end, same shape as the ARC bug, even
    # though the real content scored well above the rerank floor once actually searched under the
    # correct topic (mckinley.illinois.edu/hours, mckinley.illinois.edu/fees/health-service-fee;
    # dres.illinois.edu/faculty-staff, .../community/accessibility-transportation/accessible-
    # parking, .../community/accessibility-transportation/wheelchair-rental).
    Topic.HEALTH_WELLNESS: (
        "McKinley Health Center's hours on weekends",
        "whether counseling is covered by the mandatory student health fee",
    ),
    Topic.ACCESSIBILITY_DISABILITY_SUPPORT: (
        "getting extended time on exams as a disability accommodation",
        # "Is there accessible parking near the dorms?" (150-question sweep) was going to get an
        # exemplar here too, but every wording tried ("accessible parking permits...", "wheelchair-
        # accessible parking spaces...") either failed to beat TRANSPORTATION_PARKING's own strong
        # pull for this exact query (0.7249, unmoved by any of them) or caused new regressions on
        # plain parking queries -- reverted as net-negative rather than kept; see
        # topic_regression_set.py's xfail_reason for this one instead of forcing it here.
        "renting a wheelchair through DRES",
    ),
    Topic.ADMISSIONS: (
        "admission selectivity and acceptance rates by department",
        "acceptance rates and selectivity for different academic colleges within UIUC",
        "what transcripts and test scores to submit for a graduate school application",
        "applying under an early action plan versus the regular decision timeline",
        "the minimum GPA cutoff to transfer in as a junior",
        "fall and spring transfer admission application deadlines",
        # Confirmed live (150-question sweep): "What's the Common App deadline for Illinois?"
        # landed on ACADEMIC_CALENDAR_GRADUATION (application deadlines read as "calendar dates")
        # over ADMISSIONS, and that wrong topic had enough of its own documents to dodge the
        # topic_filter_min_results relaxation -- same dead-end shape as the ARC bug. Two earlier
        # drafts each caused a new collision, caught by the full suite before being committed:
        # "...deadline to submit to Illinois" (lost "What's the Illinois Commitment and am I
        # eligible?" to this topic) and "...for first-year admission to Illinois" (lost "What's
        # the closest airport to Champaign-Urbana?" to this topic). Verified clean against both
        # before landing this wording.
        "the submission deadline on the Common Application platform for freshman applicants",
    ),
    Topic.ACADEMIC_ADVISING: (
        "the paperwork to officially declare or switch your major within LAS",
    ),
    # CAMPUS_RECREATION's plain description ("gym, pool, fitness facilities, recreation center
    # membership, ...") already covers "membership" and "recreation center" as concepts, but
    # scored 0.544 for a real live query phrased as "membership to the ARC" -- STUDENT_
    # ORGANIZATIONS_ENGAGEMENT's much shorter, more generic description ("student clubs and
    # registered student organizations") scored higher (0.617) on the same query purely from
    # embedding-similarity noise, since neither topic has any exemplars and the description
    # alone doesn't anchor "ARC" (the Activities & Recreation Center's actual, commonly-used
    # name) to "membership" as one concrete phrase. Confirmed live: retrieval then filtered to
    # the (wrong) student-orgs topic, which has enough of its own documents to clear
    # topic_filter_min_results without ever relaxing, and none of them scored above
    # min_rerank_score -- "I couldn't find anything" for a question the corpus actually answers
    # (campusrec.illinois.edu/membership, campusrec.illinois.edu/facilities). One exemplar
    # anchoring the real phrasing, not a description rewrite -- narrower risk of diluting other
    # topics per this file's own established exemplar-over-description-edit convention.
    Topic.CAMPUS_RECREATION: (
        "getting a membership to the ARC or another recreation facility",
        # Both confirmed live (150-question sweep), same dead-end shape as the ARC bug above --
        # each landed on a wrong topic with enough of its own documents to dodge relaxation.
        "the difference between the ARC and CRCE recreation facilities",
        "renting outdoor gear like kayaks or camping equipment from campus recreation",
    ),
    # No exemplars existed for this topic before -- relied solely on its plain description
    # ("student clubs and registered student organizations"). Confirmed live (150-question sweep):
    # both queries below landed on a wrong topic confident and thin-relaxation-proof enough to
    # dead-end, same shape as the ARC bug.
    Topic.STUDENT_ORGANIZATIONS_ENGAGEMENT: (
        "joining a registered student organization (RSO)",
        "the rules for tabling or promoting your student org on the quad",
    ),
    Topic.ACADEMICS: (
        "using the course explorer tool to plan out your class schedule",
        "how many times you're allowed to retake a class you previously failed",
        "auditing a course instead of taking it for a grade",
    ),
    # Regressed once this topic's description merged the old ACADEMIC_CALENDAR content with
    # graduation/commencement content into one longer string -- semester-date-specific queries
    # (with no graduation-related wording to anchor them) started losing to ADMISSIONS,
    # ORIENTATION_NEW_STUDENTS, and REGISTRATION_RECORDS instead.
    Topic.ACADEMIC_CALENDAR_GRADUATION: (
        "the specific dates fall break falls on this academic year",
        "what day the spring semester officially ends",
        "whether there's a reading day scheduled before final exams begin",
        "when final grades get posted after finals week is over",
        "the first day of classes for the fall semester",
        # Deliberately just "what the add/drop deadline is" -- a closer paraphrase ("the last
        # day you're allowed to add or drop a class without penalty") was tried and reverted: it
        # collided with two REGISTRATION_RECORDS-expected cases about the same add/drop mechanic
        # phrased slightly differently ("What's the last day to drop a class without a W?",
        # "What's the penalty for a late add/drop request?"), a genuinely close pair the new
        # taxonomy splits by intent (calendar deadline vs. registration mechanics) that this
        # embedding-similarity approach can't always disambiguate -- documented as a residual in
        # topic_regression_set.py rather than chased further.
        "what the add/drop deadline is",
    ),
    # Regressed for the same reason as CAMPUS_SERVICES_FACILITIES's other content diluting
    # this topic's course-catalog wording (see topic_classifier.py's comment on that topic's
    # ambiguity with ACADEMICS): "Where can I find the course catalog?" was losing to ACADEMICS
    # instead, whose Course Explorer/grades wording is a near-neighbor concept.
    Topic.CAMPUS_SERVICES_FACILITIES: (
        "finding the official course catalog listing for a specific academic department",
    ),
    # "How do I check my registration appointment time?" and "Can I skip New Student
    # Registration if I've already registered for classes?" regressed when this topic's
    # description grew to merge the old REGISTRATION and COURSE_REGISTRATION content into one
    # longer string -- same dilution failure mode as CAREER_EMPLOYMENT below. A third exemplar
    # tried here ("whether you have to attend orientation before you're able to register for
    # classes") was reverted: it fixed its one target case but broke 7 separate
    # ORIENTATION_NEW_STUDENTS cases by sharing too much "orientation" wording with them --
    # exactly the over-broad-exemplar risk this file's docs warn about, not worth the trade.
    Topic.REGISTRATION_RECORDS: (
        "dropping a class late enough that it leaves a W mark instead of "
        "disappearing from your record",
        "voluntarily blocking yourself from registering for classes",
        "requesting a leave of absence to step away from your studies for a term",
        "checking your assigned time slot to register for classes",
        "whether completing New Student Registration is different from registering for classes",
        # Three confirmed live (150-question sweep), same dead-end shape as the ARC bug: each
        # landed on a wrong topic with enough of its own documents to dodge relaxation, while the
        # real content (registrar.illinois.edu/registration-checklist, .../changing-your-personal-
        # information-2, .../academic-records-faq) scored well above the rerank floor once
        # actually searched under this topic.
        # Two earlier drafts ("...student account...", then "...registration hold on your
        # record...") each shared enough vocabulary to start winning an unrelated query away
        # from its real topic ("How much storage do I get with my university email account?" from
        # TECHNOLOGY_SERVICES, then "What's the process to appeal a parking ticket?" from
        # TRANSPORTATION_PARKING) -- each caught by the full suite before being committed.
        # Verified clean against both collisions before landing this wording.
        "why you can't register for classes because of a hold on your record",
        "changing your legal name in the university's academic records system",
        # "...your parents..." (an earlier draft) collided with "Can my parents attend
        # orientation with me?" -- caught by the full suite before this was committed.
        # "family members" instead, since FERPA's own real scope isn't parent-specific anyway.
        "whether family members are allowed to view your academic grades under FERPA",
    ),
    Topic.TECHNOLOGY_SERVICES: (
        "resetting a forgotten NetID or university account password",
        "getting a replacement student identification card after losing yours",
    ),
    Topic.CAREER_EMPLOYMENT: (
        "finding and interviewing for an open graduate assistantship position in a department",
        # Regression found when this topic's description grew to merge the old CAREER_SERVICES
        # and STUDENT_EMPLOYMENT content into one longer string: "How many hours can I work as a
        # student employee?" started losing to REGISTRATION_RECORDS without this exemplar.
        "the maximum number of hours a student employee is allowed to work per week",
        # Four further exemplars (resume review, on-campus job search, work study, international
        # student work eligibility, financial-aid interaction) were tried here and reverted:
        # each fixed its own one target query but collectively turned this topic into an
        # over-broad attractor that started winning several unrelated queries instead ("How do I
        # apply for on-campus housing?", "How do I apply for financial aid?", "Does the
        # university offer peer tutoring?" all started losing to CAREER_EMPLOYMENT once those
        # exemplars were added). Reverted as net-negative rather than kept -- see
        # topic_regression_set.py for the resulting documented residuals.
    ),
    Topic.ORIENTATION_NEW_STUDENTS: (
        "is attending Welcome Week mandatory before you can pick your classes",
        # "Is there a specific orientation for international students?" (150-question sweep) was
        # going to get an exemplar here too -- four wordings were tried, and each fixed the target
        # while causing a *different* new collision, caught by the full suite before being
        # committed each time: "...a separate orientation program specifically for international
        # students" and "...a separate New Student Registration session just for incoming
        # international students" both sat in too broad a "student services/programs"
        # neighborhood (won "Can I apply as a second bachelor's degree student?", "Does the
        # university offer peer tutoring?", "Does ISSS help with cultural adjustment?" instead);
        # "...register for orientation on a different schedule" collided with "Do I need to
        # complete registration before orientation?"; "a distinct orientation track..." then
        # un-fixed an unrelated, already-passing case ("What happens if I miss my orientation
        # session?") on top of a fifth new collision. Reverted as net-negative rather than kept,
        # same call this file already made once for a CAREER_EMPLOYMENT exemplar batch above --
        # see topic_regression_set.py's xfail_reason for this one instead of forcing it here.
    ),
    # This topic's description merged four previously-separate, individually-tuned descriptions
    # (VISA, CPT, OPT, INTERNATIONAL_STUDENT_SERVICES) into one -- by far the largest merge in
    # this migration. An initial batch of 14 exemplars (one per CPT/OPT/SEVIS/I-20/visa-mechanics
    # query that regressed) fixed all of those but turned this topic into an over-broad attractor
    # that started winning 8+ unrelated queries across other topics instead (career coaching,
    # on-campus jobs, IT help, parking permits, health insurance, academic advising, dining --
    # see topic_regression_set.py's xfail_reason entries for the full list). Trimmed down to just
    # the three VISA-subtopic exemplars, which fixed their targets without detectable collateral
    # damage against the full suite; the CPT/OPT-specific ones were reverted as net-negative --
    # those queries still get a plausible (if imprecise) answer via this topic's own CPT/OPT
    # wording in the description above, or are documented as residuals.
    Topic.INTERNATIONAL_STUDENTS_IMMIGRATION: (
        "the ISSS pre-departure checklist of items to bring to the US as a "
        "new international student",
        "what to do if there's an error on your I-20 form",
        "what SEVIS is and why it matters for your immigration status",
        "whether your visa expires if you stay in the US past your program end date",
        # "what is CPT" alone scored 0.543 (just under the 0.55 threshold) found via the golden
        # set (app/evaluation/golden_set.py's international_cpt case), same bare-acronym pattern
        # as "what is OPT" already in the description above -- given its own exemplar rather than
        # folded into the (already long) description, so it isn't diluted by the rest of it.
        "what is CPT",
        # Two more confirmed live (150-question sweep), same dead-end shape as the ARC bug. Kept
        # tightly scoped to OPT mechanics specifically, given this topic's documented history of
        # becoming an over-broad attractor above -- not a repeat of the reverted 14-exemplar batch.
        "traveling internationally while on OPT",
        "how long you're allowed to stay in the US after graduating on OPT",
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
def _topic_embeddings() -> dict[Topic, list[list[float]]]:
    """Every topic's primary description, plus any exemplars, each
    embedded separately -- see _TOPIC_EXEMPLARS' comment for why these
    aren't merged into one string per topic."""
    embedder = Embedder()
    texts: list[str] = []
    owners: list[Topic] = []
    for topic in _TOPIC_DESCRIPTIONS:
        texts.append(_TOPIC_DESCRIPTIONS[topic])
        owners.append(topic)
        for exemplar in _TOPIC_EXEMPLARS.get(topic, ()):
            texts.append(exemplar)
            owners.append(topic)

    vectors = embedder.embed_documents(texts)
    result: dict[Topic, list[list[float]]] = {topic: [] for topic in _TOPIC_DESCRIPTIONS}
    for owner, vector in zip(owners, vectors, strict=True):
        result[owner].append(vector)
    return result


class TopicClassifier:
    """Classifies a message into a Topic by embedding similarity, with a
    confidence score the caller uses to decide whether to trust it or ask
    for clarification instead of guessing.

    Deliberately predicts only the top-level Topic, not a (topic, subtopic)
    pair -- Document.subtopic (Source Manifest V2's category-level
    subtopic, e.g. "OPT" under INTERNATIONAL_STUDENTS_IMMIGRATION) is set
    only by SourceConfig entries and scripts/remap_topics_v2.py's
    department/URL heuristics, not predicted here. Doubling this
    classifier to also predict subtopic would meaningfully increase its
    tuning surface for a feature nothing downstream currently reads
    subtopic for at query time (see app/graph/nodes.py -- retrieval
    filters only ever key on topic).
    """

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
        for topic, vectors in topic_vectors.items():
            score = max(_cosine(query_vector, vector) for vector in vectors)
            if score > best_score:
                best_topic, best_score = topic, score

        if best_score < self._threshold:
            return TopicClassification(topic=None, confidence=best_score)
        return TopicClassification(topic=best_topic, confidence=best_score)
