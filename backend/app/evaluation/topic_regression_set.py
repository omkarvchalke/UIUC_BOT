"""307-case topic-classification regression set: for every case, the
*genuinely correct* topic for that message, hand-verified against the real
taxonomy and the real corpus organization -- not what TopicClassifier
currently happens to return. See tests/retrieval/test_topic_regression.py,
which runs every case directly against TopicClassifier() (no live backend,
no LLM, no network -- classification is 100% local embeddings, so this runs
in the normal fast suite).

xfail_reason is non-empty for cases TopicClassifier currently, verifiably
gets wrong (confirmed live when this set was built) -- these are real,
tracked gaps, not test bugs, following the same "known limitation, not yet
fixed" documentation style as app/evaluation/golden_set.py and the
doctor's-appointment-vs-dining comment in topic_classifier.py. Marked
strict=True in the test, so if a future topic_classifier.py change happens
to fix one, pytest reports an XPASS failure -- that's the signal to delete
the xfail_reason, not a bug in the test.

This set has driven five rounds of fixes so far, each verified against the
full accumulated suite before being applied (see topic_classifier.py's
comments on Topic.TRANSPORTATION_PARKING, Topic.REGISTRATION_RECORDS, the
REGISTRATION-attractor-cluster follow-up round, the 39-xfail follow-up
round, and _TOPIC_EXEMPLARS -- a structural change introduced in the fifth
round after five specific topics (ADMISSIONS, ACADEMIC_CALENDAR,
FINANCIAL_AID, SCHOLARSHIPS, COURSE_REGISTRATION) had resisted every
_TOPIC_DESCRIPTIONS wording change attempted across three rounds).
Exemplars let a topic match on several independently-scored short phrases
instead of one shared description string, so a phrase added for one
narrow query can't dilute that topic's other, already-passing queries --
this fixed 18 of that round's 29 xfails, including several in
COURSE_REGISTRATION, previously the single most fragile topic under
description edits.

The 11 cases that remain xfail after five rounds were each attempted
multiple times (up to 7-8 differently-worded exemplars for the hardest
ones) and kept causing new regressions regardless of phrasing. Four of
them (queries that should trigger clarification, not a topic match) are
structurally unfixable by the exemplar mechanism: exemplars only ever add
matching power to a topic, so they can raise a topic's own recall but can
never suppress another topic's false-positive score on a vague or
off-topic message.

A confidence-margin check (requiring the top score to beat the runner-up
by some minimum gap, not just clear the absolute 0.55 threshold) was
investigated as the natural next mechanism for exactly these 4 cases --
and rejected before ever touching the classifier, based on the real
margin distribution across this suite. The margin does not correlate
with correctness here: over a dozen genuinely CORRECT classifications
win by a margin of 0.001-0.005 (e.g. "How do I renew my F-1 visa?" beats
its runner-up by 0.001), tighter than 3 of the 4 target cases. A margin
threshold loose enough to spare those correct cases wouldn't catch "tell
me about stuff" (margin 0.006) either. Raising the absolute threshold
instead doesn't work any better: "What mental health resources are
available to students?" scores 0.624, but 45 separate CORRECT
classifications also fall in the 0.55-0.63 range, so excluding it would
turn 45 good answers into unnecessary clarifying questions. These 4 are
accepted as permanent residuals of the current design (per-topic cosine
similarity against a fixed set of vectors, argmax with one global
threshold) rather than a gap waiting for the right threshold tweak --
a real fix would need a fundamentally different signal than more
vectors or a different cutoff on the same score.

A handful of messages that look like plausible test cases were
deliberately excluded, not included as extra cases:
- "hello" / "hi there" / "thanks, that's helpful": true greetings never
  reach TopicClassifier in production -- app.graph.nodes.intent_detection
  intercepts them first via a rule-based greeting check. Testing them here
  would be testing the wrong component.
- A number of genuinely ambiguous cases where more than one topic is
  defensible for the same question (e.g. "What is the difference between
  CPT and OPT?", "What is a registration hold?") -- asserting one "correct"
  answer for those would test my judgment call, not the classifier's
  correctness.
"""

from dataclasses import dataclass

from app.models.document import Topic


@dataclass(frozen=True)
class TopicCase:
    """One (message, correct Topic) pair. expected_topic is None for
    messages that should not confidently match any topic (genuinely
    off-topic or too vague), which is what should trigger a clarifying
    question in the live app rather than a wrong-topic guess."""

    message: str
    expected_topic: Topic | None
    xfail_reason: str = ""


TOPIC_REGRESSION_SET: tuple[TopicCase, ...] = (
    TopicCase("What GPA do I need to get into UIUC as a freshman?", Topic.ADMISSIONS),
    TopicCase("What are the application deadlines for freshman admission?", Topic.ADMISSIONS),
    TopicCase("What essays do I need to write for my UIUC application?", Topic.ADMISSIONS),
    TopicCase("How do I apply as a transfer student?", Topic.ADMISSIONS),
    TopicCase("What GPA do I need to transfer to UIUC?", Topic.ADMISSIONS),
    TopicCase("What are the requirements for graduate admission?", Topic.ADMISSIONS),
    TopicCase(
        "How do international students apply for undergraduate admission?",
        Topic.ADMISSIONS,
        xfail_reason=(
            "migration to Source Manifest V2 taxonomy: loses to FINANCIAL_AID_SCHOLARSHIPS "
            "[currently: financial_aid_scholarships, 0.721]"
        ),
    ),
    TopicCase("What documents do I need to complete my graduate application?", Topic.ADMISSIONS),
    TopicCase("Can I apply as a second bachelor's degree student?", Topic.ADMISSIONS),
    TopicCase("What's the acceptance rate for freshman applicants?", Topic.ADMISSIONS),
    TopicCase("Is UIUC test-optional for admissions?", Topic.ADMISSIONS),
    TopicCase("Can I transfer in with an associate's degree?", Topic.ADMISSIONS),
    # Regression found via a live 200-question sweep, not the offline
    # suite itself: this exact phrasing wasn't one of the 306 cases, so
    # nothing caught it when SCHOLARSHIPS gained a "transfer students"
    # exemplar in a prior round and started winning this query instead
    # (both matched on "transfer(ring)"). Added here specifically so a
    # repeat of this collision is caught offline next time.
    TopicCase("I'm a junior transferring in, what's my GPA cutoff?", Topic.ADMISSIONS),
    # Regression found via a live 326-question sweep (masked until then by
    # an unrelated generation bug that made every answer look "grounded"
    # regardless of retrieval quality): "What are the transfer application
    # deadlines?" scored SCHOLARSHIPS 0.6822 vs ADMISSIONS 0.6764 --
    # SCHOLARSHIPS' "scholarship application deadlines" phrasing (added for
    # a different query) shares the same "[X] application deadlines"
    # structure. Fixed with a new ADMISSIONS exemplar; added here so a
    # repeat of this collision is caught offline next time.
    TopicCase("What are the transfer application deadlines?", Topic.ADMISSIONS),
    TopicCase("What's the average class size for incoming freshmen?", Topic.ADMISSIONS),
    TopicCase(
        "How selective is the College of Engineering for freshman applicants?",
        Topic.ADMISSIONS,
    ),
    TopicCase("Is there an application fee for freshman admission?", Topic.ADMISSIONS),
    TopicCase(
        "Can I defer my admission to a later semester?",
        Topic.ADMISSIONS,
        xfail_reason=("loses to ACADEMIC_CALENDAR [currently: course_registration, 0.692]"),
    ),
    TopicCase("Do I need letters of recommendation to apply?", Topic.ADMISSIONS),
    TopicCase(
        "What's the difference between early action and regular decision?",
        Topic.ADMISSIONS,
    ),
    # Real live failure (150-question sweep, confirmed via /retrieve): dead-ended the same way
    # the ARC bug did before the dedicated exemplar above was added.
    TopicCase("What's the Common App deadline for Illinois?", Topic.ADMISSIONS),
    TopicCase("How do I register as a new student?", Topic.REGISTRATION_RECORDS),
    TopicCase("What is New Student Registration?", Topic.REGISTRATION_RECORDS),
    TopicCase("When can continuing students register for classes?", Topic.REGISTRATION_RECORDS),
    TopicCase("How do I register for New Student Registration as a transfer?", Topic.REGISTRATION_RECORDS),
    TopicCase("Do I need to complete registration before orientation?", Topic.REGISTRATION_RECORDS),
    TopicCase("What happens during New Student Registration?", Topic.REGISTRATION_RECORDS),
    TopicCase("Is New Student Registration mandatory?", Topic.REGISTRATION_RECORDS),
    TopicCase("How do I check my registration appointment time?", Topic.REGISTRATION_RECORDS),
    TopicCase(
        "Do continuing students need to register every semester?",
        Topic.REGISTRATION_RECORDS,
    ),
    TopicCase(
        "What's the difference between new student registration and regular registration?",
        Topic.REGISTRATION_RECORDS,
    ),
    TopicCase("Is there a fee for New Student Registration?", Topic.REGISTRATION_RECORDS),
    # Fixed by the taxonomy migration itself: REGISTRATION and COURSE_REGISTRATION merged
    # into one topic (REGISTRATION_RECORDS), so this compound query naming both senses of
    # "register" no longer has two competing topics to lose between.
    TopicCase(
        "Can I skip New Student Registration if I've already registered for classes?",
        Topic.REGISTRATION_RECORDS,
    ),
    TopicCase(
        "How do I get a letter confirming my enrollment status?",
        Topic.REGISTRATION_RECORDS,
        xfail_reason=(
            "migration to Source Manifest V2 taxonomy: loses to FINANCIAL_AID_SCHOLARSHIPS "
            "[currently: financial_aid_scholarships, 0.732]"
        ),
    ),
    TopicCase(
        "Where do continuing students go to check their registration time slot?",
        Topic.REGISTRATION_RECORDS,
    ),
    TopicCase("Do I have to sign up for NSR before I move in?", Topic.REGISTRATION_RECORDS),
    TopicCase("What is the process for requesting a leave of absence?", Topic.REGISTRATION_RECORDS),
    TopicCase("What is Welcome Week?", Topic.ORIENTATION_NEW_STUDENTS),
    TopicCase("Is orientation mandatory for freshmen?", Topic.ORIENTATION_NEW_STUDENTS),
    TopicCase("What happens at international student orientation?", Topic.ORIENTATION_NEW_STUDENTS),
    TopicCase("When is orientation for transfer students?", Topic.ORIENTATION_NEW_STUDENTS),
    TopicCase("What should I bring to orientation?", Topic.ORIENTATION_NEW_STUDENTS),
    TopicCase("Can my parents attend orientation with me?", Topic.ORIENTATION_NEW_STUDENTS),
    TopicCase("How long does orientation last?", Topic.ORIENTATION_NEW_STUDENTS),
    TopicCase("Do graduate students have an orientation?", Topic.ORIENTATION_NEW_STUDENTS),
    TopicCase("What's Welcome Week actually like?", Topic.ORIENTATION_NEW_STUDENTS),
    TopicCase("Is there a virtual orientation option?", Topic.ORIENTATION_NEW_STUDENTS),
    TopicCase("What topics are covered during Welcome Week programming?", Topic.ORIENTATION_NEW_STUDENTS),
    # Real live failure (150-question sweep, confirmed via /retrieve: dead-ends the same way the
    # ARC bug did). Every exemplar wording tried in topic_classifier.py fixed this one query while
    # causing a different collision each time (5 rounds) -- documented residual, not silently
    # dropped; see topic_classifier.py's ORIENTATION_NEW_STUDENTS comment for the full history.
    TopicCase(
        "Is there a specific orientation for international students?",
        Topic.ORIENTATION_NEW_STUDENTS,
        xfail_reason=(
            "150-question sweep: loses to FINANCIAL_AID_SCHOLARSHIPS "
            "[currently: financial_aid_scholarships, 0.701]"
        ),
    ),
    # Fixed by the taxonomy migration itself, same reasoning as the New Student Registration
    # case above: COURSE_REGISTRATION no longer exists as a separate topic to lose to.
    TopicCase(
        "Do I need to attend orientation before I can register for classes?",
        Topic.ORIENTATION_NEW_STUDENTS,
    ),
    TopicCase(
        "What happens if I miss my orientation session?",
        Topic.ORIENTATION_NEW_STUDENTS,
        xfail_reason=(
            "migration to Source Manifest V2 taxonomy: loses to REGISTRATION_RECORDS "
            "[currently: registration_records, 0.652]"
        ),
    ),
    TopicCase("Where do freshmen live on campus?", Topic.HOUSING),
    TopicCase("Are freshmen required to live in the dorms?", Topic.HOUSING),
    TopicCase("How do I apply for on-campus housing?", Topic.HOUSING),
    TopicCase("What are living-learning communities?", Topic.HOUSING),
    TopicCase("Can transfer students live in the dorms?", Topic.HOUSING),
    TopicCase("What residence halls are available for graduate students?", Topic.HOUSING),
    TopicCase("How much does on-campus housing cost?", Topic.HOUSING),
    TopicCase("What is the move-in process like?", Topic.HOUSING),
    TopicCase("What special living options are available?", Topic.HOUSING),
    TopicCase("Will I be assigned a specific dorm or do I pick?", Topic.HOUSING),
    TopicCase("Is it true freshmen have to live in dorms their first year?", Topic.HOUSING),
    TopicCase("Can I live off campus as a freshman?", Topic.HOUSING),
    TopicCase("What is the cost of a single dorm room?", Topic.HOUSING),
    TopicCase("How do I find a roommate?", Topic.HOUSING),
    TopicCase("How do dorm room assignments work?", Topic.HOUSING),
    TopicCase("Can I request a specific residence hall?", Topic.HOUSING),
    TopicCase("What's included in a standard dorm room?", Topic.HOUSING),
    TopicCase("Is there air conditioning in the dorms?", Topic.HOUSING),
    TopicCase("What's the difference between a double and a single dorm room?", Topic.HOUSING),
    TopicCase("Do graduate students live in the same dorms as undergrads?", Topic.HOUSING),
    TopicCase("How do I cancel my housing contract?", Topic.HOUSING),
    TopicCase(
        "What's the difference between a residence hall and an apartment-style dorm?",
        Topic.HOUSING,
    ),
    TopicCase("Is there a curfew in the dorms?", Topic.HOUSING),
    TopicCase("Does UIUC offer single-occupancy dorm rooms for an extra fee?", Topic.HOUSING),
    TopicCase(
        "What's the earliest I can move into the dorms before classes start?",
        Topic.HOUSING,
    ),
    TopicCase("What meal plans are available?", Topic.DINING),
    TopicCase("What is the difference between Classic Meals and Dining Dollars?", Topic.DINING),
    TopicCase("Are there vegetarian options in the dining halls?", Topic.DINING),
    TopicCase("How many dining halls are on campus?", Topic.DINING),
    TopicCase("Can I use my meal plan off campus?", Topic.DINING),
    TopicCase("What are the dining hall hours?", Topic.DINING),
    TopicCase("Do I need a meal plan if I live in an apartment?", Topic.DINING),
    TopicCase("What's the cheapest meal plan?", Topic.DINING),
    TopicCase(
        "What happens to unused Dining Dollars at the end of the year?",
        Topic.DINING,
        xfail_reason=(
            "migration to Source Manifest V2 taxonomy: loses to INTERNATIONAL_STUDENTS_IMMIGRATION "
            "[currently: international_students_immigration, 0.670]"
        ),
    ),
    TopicCase("What's included in Dining Dollars?", Topic.DINING),
    TopicCase("What's the cost of an on-campus meal plan per semester?", Topic.DINING),
    TopicCase("Are there gluten-free options in the dining halls?", Topic.DINING),
    TopicCase("Can I get food delivered to my dorm through the meal plan?", Topic.DINING),
    TopicCase("Are there halal or kosher dining options?", Topic.DINING),
    TopicCase("What's the meal plan cancellation policy?", Topic.DINING),
    TopicCase("How do dining dollars roll over between semesters?", Topic.DINING),
    TopicCase("How much is out-of-state tuition?", Topic.FINANCIAL_AID_SCHOLARSHIPS),
    TopicCase("How do I apply for financial aid?", Topic.FINANCIAL_AID_SCHOLARSHIPS),
    TopicCase("What is the FAFSA deadline?", Topic.FINANCIAL_AID_SCHOLARSHIPS),
    TopicCase("What types of financial aid does UIUC offer?", Topic.FINANCIAL_AID_SCHOLARSHIPS),
    TopicCase("How do I pay my tuition bill?", Topic.FINANCIAL_AID_SCHOLARSHIPS),
    TopicCase("What is the Illinois Commitment program?", Topic.FINANCIAL_AID_SCHOLARSHIPS),
    # Corrected to FINANCIAL_AID_COSTS: Source Manifest V2 splits registrar billing/refund
    # content into its own topic (see topic_classifier.py's comment on FINANCIAL_AID_COSTS) --
    # this case's expected topic was stale from the bulk old-taxonomy remap, not a real
    # classifier regression.
    TopicCase("Are there refund options for overpayment?", Topic.FINANCIAL_AID_COSTS),
    TopicCase("What banking options are available through the i-card?", Topic.FINANCIAL_AID_SCHOLARSHIPS),
    TopicCase("What is the average cost of textbooks?", Topic.FINANCIAL_AID_SCHOLARSHIPS),
    # Corrected to CAMPUS_SERVICES_FACILITIES: Source Manifest V2 classifies the actual bookstore
    # pages there, not under either financial-aid topic (see
    # app/ingestion/domains/graduation_records.py's comment on this exact migration decision) --
    # same "stale from bulk remap" reasoning as the overpayment case above.
    TopicCase("Where do I buy textbooks?", Topic.CAMPUS_SERVICES_FACILITIES),
    TopicCase(
        "Can I get a refund if I overpay my tuition bill?",
        Topic.FINANCIAL_AID_COSTS,
        xfail_reason=(
            "migration to Source Manifest V2 taxonomy: loses to FINANCIAL_AID_SCHOLARSHIPS "
            "[currently: financial_aid_scholarships, 0.728]"
        ),
    ),
    TopicCase("What's the Illinois Commitment and am I eligible?", Topic.FINANCIAL_AID_SCHOLARSHIPS),
    TopicCase("How much financial aid will I get?", Topic.FINANCIAL_AID_SCHOLARSHIPS),
    TopicCase("What is the net price calculator?", Topic.FINANCIAL_AID_SCHOLARSHIPS),
    # Fixed by the taxonomy migration itself: SCHOLARSHIPS merged into this same topic
    # (FINANCIAL_AID_SCHOLARSHIPS), so "loses to SCHOLARSHIPS" is no longer a possible outcome.
    TopicCase("How do I check my financial aid award status?", Topic.FINANCIAL_AID_SCHOLARSHIPS),
    TopicCase("Are there payment plans for tuition?", Topic.FINANCIAL_AID_SCHOLARSHIPS),
    TopicCase("What's a Pell Grant?", Topic.FINANCIAL_AID_SCHOLARSHIPS),
    # Fixed live (now scores FINANCIAL_AID_SCHOLARSHIPS 0.887 outright) even though
    # INTERNATIONAL_STUDENTS_IMMIGRATION (the old competitor's merged successor topic) is still a
    # separate topic here -- the new FINANCIAL_AID_SCHOLARSHIPS description apparently strengthened
    # enough during this migration's other fixes to win this case cleanly.
    TopicCase("Do international students qualify for financial aid?", Topic.FINANCIAL_AID_SCHOLARSHIPS),
    TopicCase("Is the Illinois Commitment scholarship need-based?", Topic.FINANCIAL_AID_SCHOLARSHIPS),
    TopicCase("Can I get a tuition waiver as a graduate assistant?", Topic.FINANCIAL_AID_SCHOLARSHIPS),
    TopicCase("What scholarships are available for incoming freshmen?", Topic.FINANCIAL_AID_SCHOLARSHIPS),
    TopicCase(
        "Do I need to submit a separate application for merit scholarships?",
        Topic.FINANCIAL_AID_SCHOLARSHIPS,
    ),
    TopicCase("Are there scholarships for transfer students?", Topic.FINANCIAL_AID_SCHOLARSHIPS),
    TopicCase("What is the deadline to apply for scholarships?", Topic.FINANCIAL_AID_SCHOLARSHIPS),
    TopicCase("Are scholarships renewable each year?", Topic.FINANCIAL_AID_SCHOLARSHIPS),
    TopicCase("Where can I find a list of available scholarships?", Topic.FINANCIAL_AID_SCHOLARSHIPS),
    TopicCase("Is there a merit scholarship I should apply for separately?", Topic.FINANCIAL_AID_SCHOLARSHIPS),
    TopicCase("Can I combine multiple scholarships?", Topic.FINANCIAL_AID_SCHOLARSHIPS),
    TopicCase("Do departmental scholarships require a separate application?", Topic.FINANCIAL_AID_SCHOLARSHIPS),
    TopicCase(
        "How do I find an on-campus job?",
        Topic.CAREER_EMPLOYMENT,
        xfail_reason=(
            "migration to Source Manifest V2 taxonomy: loses to TECHNOLOGY_SERVICES "
            "[currently: technology_services, 0.681]"
        ),
    ),
    TopicCase(
        "What is work study?",
        Topic.CAREER_EMPLOYMENT,
        xfail_reason=(
            "migration to Source Manifest V2 taxonomy: loses to ACADEMICS "
            "[currently: academics, 0.563]"
        ),
    ),
    TopicCase(
        "Can international students work on campus?",
        Topic.CAREER_EMPLOYMENT,
        xfail_reason=(
            "migration to Source Manifest V2 taxonomy: loses to FINANCIAL_AID_SCHOLARSHIPS "
            "[currently: financial_aid_scholarships, 0.708]"
        ),
    ),
    TopicCase("How many hours can I work as a student employee?", Topic.CAREER_EMPLOYMENT),
    TopicCase("Where do I search for campus jobs?", Topic.CAREER_EMPLOYMENT),
    TopicCase("What is Hire Illini?", Topic.CAREER_EMPLOYMENT),
    TopicCase("Where do I look for part-time jobs on campus?", Topic.CAREER_EMPLOYMENT),
    TopicCase(
        "What's the maximum number of hours a work-study student can work?",
        Topic.CAREER_EMPLOYMENT,
    ),
    TopicCase("Can I have more than one on-campus job at a time?", Topic.CAREER_EMPLOYMENT),
    TopicCase("How do I apply for a graduate assistantship?", Topic.CAREER_EMPLOYMENT),
    TopicCase(
        "Does working on campus affect my financial aid?",
        Topic.CAREER_EMPLOYMENT,
        xfail_reason=(
            "migration to Source Manifest V2 taxonomy: loses to FINANCIAL_AID_SCHOLARSHIPS "
            "[currently: financial_aid_scholarships, 0.688]"
        ),
    ),
    TopicCase(
        "What's the difference between a graduate assistantship and work study?",
        Topic.CAREER_EMPLOYMENT,
    ),
    TopicCase(
        "What services does ISSS provide for international students?",
        Topic.INTERNATIONAL_STUDENTS_IMMIGRATION,
    ),
    TopicCase(
        "Who do I contact for international student support?",
        Topic.INTERNATIONAL_STUDENTS_IMMIGRATION,
        xfail_reason=(
            "migration to Source Manifest V2 taxonomy: loses to FINANCIAL_AID_SCHOLARSHIPS "
            "[currently: financial_aid_scholarships, 0.674]"
        ),
    ),
    TopicCase(
        "What resources are available for international students on campus?",
        Topic.INTERNATIONAL_STUDENTS_IMMIGRATION,
    ),
    TopicCase(
        "What should international students do before they arrive on campus?",
        Topic.INTERNATIONAL_STUDENTS_IMMIGRATION,
    ),
    TopicCase(
        "What documents should I bring when I first arrive at UIUC?",
        Topic.INTERNATIONAL_STUDENTS_IMMIGRATION,
        xfail_reason=("loses to ADMISSIONS [currently: admissions, 0.766]"),
    ),
    TopicCase(
        "What does ISSS stand for and what do they do?",
        Topic.INTERNATIONAL_STUDENTS_IMMIGRATION,
    ),
    TopicCase("Does ISSS help with cultural adjustment?", Topic.INTERNATIONAL_STUDENTS_IMMIGRATION),
    TopicCase(
        "How do I get a letter from ISSS for a bank account?",
        Topic.INTERNATIONAL_STUDENTS_IMMIGRATION,
    ),
    TopicCase("What is a Form I-20?", Topic.INTERNATIONAL_STUDENTS_IMMIGRATION),
    TopicCase("How do I maintain my F-1 visa status?", Topic.INTERNATIONAL_STUDENTS_IMMIGRATION),
    TopicCase("What documents do I need for my visa interview?", Topic.INTERNATIONAL_STUDENTS_IMMIGRATION),
    TopicCase("What happens if my I-20 has an error?", Topic.INTERNATIONAL_STUDENTS_IMMIGRATION),
    TopicCase("How long is my visa valid while I'm a student?", Topic.INTERNATIONAL_STUDENTS_IMMIGRATION),
    TopicCase("My I-20 has a typo, what do I do?", Topic.INTERNATIONAL_STUDENTS_IMMIGRATION),
    TopicCase("How do I renew my F-1 visa?", Topic.INTERNATIONAL_STUDENTS_IMMIGRATION),
    TopicCase("What is SEVIS and why does it matter?", Topic.INTERNATIONAL_STUDENTS_IMMIGRATION),
    TopicCase("Can I travel outside the US and come back on my visa?", Topic.INTERNATIONAL_STUDENTS_IMMIGRATION),
    TopicCase("Does my visa expire if I stay in the US past my program end date?", Topic.INTERNATIONAL_STUDENTS_IMMIGRATION),
    TopicCase(
        "What is Curricular Practical Training?",
        Topic.INTERNATIONAL_STUDENTS_IMMIGRATION,
        xfail_reason=(
            "migration to Source Manifest V2 taxonomy: loses to STUDENT_ORGANIZATIONS_ENGAGEMENT "
            "[currently: student_organizations_engagement, 0.584]"
        ),
    ),
    # Fixed by the "what is CPT" exemplar added for the golden-set international_cpt case.
    TopicCase("How do I apply for CPT?", Topic.INTERNATIONAL_STUDENTS_IMMIGRATION),
    TopicCase(
        "Do I need my academic advisor's approval for CPT?",
        Topic.INTERNATIONAL_STUDENTS_IMMIGRATION,
        xfail_reason=(
            "migration to Source Manifest V2 taxonomy: loses to ACADEMIC_ADVISING "
            "[currently: academic_advising, 0.710]"
        ),
    ),
    # These three, and the two just above/below, were all fixed by the same "what is CPT"
    # exemplar added for the golden-set international_cpt case -- CPT queries generally were
    # scoring just under threshold on this topic before it, not only the bare "what is CPT?".
    TopicCase("Can I do CPT during my first year?", Topic.INTERNATIONAL_STUDENTS_IMMIGRATION),
    TopicCase("Can I start CPT my first semester?", Topic.INTERNATIONAL_STUDENTS_IMMIGRATION),
    TopicCase(
        "How many hours of CPT can I do without affecting my OPT eligibility?",
        Topic.INTERNATIONAL_STUDENTS_IMMIGRATION,
    ),
    # Fixed by the "what is CPT" exemplar added for the golden-set international_cpt case.
    TopicCase("Does CPT require a job offer before applying?", Topic.INTERNATIONAL_STUDENTS_IMMIGRATION),
    TopicCase("Is CPT authorization tied to a specific employer?", Topic.INTERNATIONAL_STUDENTS_IMMIGRATION),
    TopicCase("How do I apply for OPT?", Topic.INTERNATIONAL_STUDENTS_IMMIGRATION),
    TopicCase("What is Optional Practical Training?", Topic.INTERNATIONAL_STUDENTS_IMMIGRATION),
    # All four fixed as an unintended side effect of the two OPT exemplars added below
    # (150-question sweep) -- each was previously xfail for losing to a different wrong topic.
    TopicCase("When can graduate students apply for OPT?", Topic.INTERNATIONAL_STUDENTS_IMMIGRATION),
    TopicCase("How long does OPT last after graduation?", Topic.INTERNATIONAL_STUDENTS_IMMIGRATION),
    TopicCase("What is the OPT filing address?", Topic.INTERNATIONAL_STUDENTS_IMMIGRATION),
    TopicCase(
        "Do grad students apply for OPT differently than undergrads?",
        Topic.INTERNATIONAL_STUDENTS_IMMIGRATION,
    ),
    TopicCase("What is STEM OPT extension?", Topic.INTERNATIONAL_STUDENTS_IMMIGRATION),
    TopicCase(
        "How soon after graduation do I need to apply for OPT?",
        Topic.INTERNATIONAL_STUDENTS_IMMIGRATION,
    ),
    TopicCase("Can I travel internationally while my OPT application is pending?", Topic.INTERNATIONAL_STUDENTS_IMMIGRATION),
    # Both real live failures (150-question sweep, confirmed via /retrieve): dead-ended the same
    # way the ARC bug did before the dedicated exemplars above were added.
    TopicCase("Can I travel home during the semester on OPT?", Topic.INTERNATIONAL_STUDENTS_IMMIGRATION),
    TopicCase("How long can I stay after I graduate on OPT?", Topic.INTERNATIONAL_STUDENTS_IMMIGRATION),
    TopicCase("How do I connect to campus WiFi?", Topic.TECHNOLOGY_SERVICES),
    TopicCase("How do I set up my university email?", Topic.TECHNOLOGY_SERVICES),
    TopicCase("Who do I contact for IT help?", Topic.TECHNOLOGY_SERVICES),
    TopicCase("Where can I buy a laptop with a student discount?", Topic.TECHNOLOGY_SERVICES),
    TopicCase("How do I get eduroam working on my laptop?", Topic.TECHNOLOGY_SERVICES),
    TopicCase("I lost my i-card, how do I get a replacement?", Topic.TECHNOLOGY_SERVICES),
    TopicCase("How do I reset my university password?", Topic.TECHNOLOGY_SERVICES),
    TopicCase(
        "What software is available for free through the university?",
        Topic.TECHNOLOGY_SERVICES,
    ),
    TopicCase(
        "How much storage do I get with my university email account?",
        Topic.TECHNOLOGY_SERVICES,
    ),
    TopicCase("Where can I print documents on campus?", Topic.TECHNOLOGY_SERVICES),
    TopicCase("What's the process for reporting a lost student ID?", Topic.TECHNOLOGY_SERVICES),
    TopicCase("What are the library hours?", Topic.LIBRARIES),
    TopicCase("How many libraries are on campus?", Topic.LIBRARIES),
    TopicCase("Can I reserve a study room in the library?", Topic.LIBRARIES),
    TopicCase("Do libraries offer virtual reality resources?", Topic.LIBRARIES),
    TopicCase("How do I check out a book from the library?", Topic.LIBRARIES),
    TopicCase("What time does the main library close on weekends?", Topic.LIBRARIES),
    TopicCase("Are there quiet study spaces in the library?", Topic.LIBRARIES),
    TopicCase("Does the library have textbooks on reserve?", Topic.LIBRARIES),
    TopicCase("Can alumni check out books from the library?", Topic.LIBRARIES),
    TopicCase("Does the library offer interlibrary loan?", Topic.LIBRARIES),
    TopicCase("What's the quietest library on campus for studying?", Topic.LIBRARIES),
    # Real live failure (150-question sweep round 2, confirmed via /retrieve): dead-ended the same
    # way the ARC bug did before the dedicated exemplar above was added.
    TopicCase("How long can I keep a book checked out?", Topic.LIBRARIES),
    TopicCase("How do I get from O'Hare Airport to UIUC without a car?", Topic.TRANSPORTATION_PARKING),
    TopicCase("What is the cheapest way to get to campus from Chicago?", Topic.TRANSPORTATION_PARKING),
    TopicCase("How much does an MTD bus pass cost?", Topic.TRANSPORTATION_PARKING),
    TopicCase("How do I get a parking permit?", Topic.TRANSPORTATION_PARKING),
    TopicCase("What are the parking rates on campus?", Topic.TRANSPORTATION_PARKING),
    TopicCase("Does UIUC have its own airport?", Topic.TRANSPORTATION_PARKING),
    TopicCase("Is the bus free for students?", Topic.TRANSPORTATION_PARKING),
    TopicCase("How do I track the campus bus in real time?", Topic.TRANSPORTATION_PARKING),
    TopicCase("Can I bring a car to campus as a freshman?", Topic.TRANSPORTATION_PARKING),
    TopicCase("How do I get from Willard Airport to campus?", Topic.TRANSPORTATION_PARKING),
    TopicCase("How do I renew my parking permit?", Topic.TRANSPORTATION_PARKING),
    TopicCase("Does UIUC have a shuttle to the airport?", Topic.TRANSPORTATION_PARKING),
    TopicCase("What's the process to appeal a parking ticket?", Topic.TRANSPORTATION_PARKING),
    TopicCase("Is there a night bus service on campus?", Topic.TRANSPORTATION_PARKING),
    TopicCase("How do I appeal a parking citation?", Topic.TRANSPORTATION_PARKING),
    TopicCase("What's the fastest way from Midway Airport to campus?", Topic.TRANSPORTATION_PARKING),
    TopicCase("Is there a campus map showing bus routes?", Topic.TRANSPORTATION_PARKING),
    TopicCase("What's the closest airport to Champaign-Urbana?", Topic.TRANSPORTATION_PARKING),
    TopicCase("Is the campus bus system free with my student ID?", Topic.TRANSPORTATION_PARKING),
    TopicCase(
        "How do I renew a parking permit that's about to expire?",
        Topic.TRANSPORTATION_PARKING,
        xfail_reason=(
            "migration to Source Manifest V2 taxonomy: loses to INTERNATIONAL_STUDENTS_IMMIGRATION "
            "[currently: international_students_immigration, 0.679]"
        ),
    ),
    TopicCase("Do I need a car as a UIUC student?", Topic.TRANSPORTATION_PARKING),
    TopicCase("Does UIUC have a bike share program?", Topic.TRANSPORTATION_PARKING),
    TopicCase("How do I get a Zipcar or campus car-share membership?", Topic.TRANSPORTATION_PARKING),
    # Both real live failures (150-question sweep round 2, confirmed via /retrieve): dead-ended
    # the same way the ARC bug did before the dedicated exemplars above were added.
    TopicCase("Can I park overnight in a student lot?", Topic.TRANSPORTATION_PARKING),
    TopicCase("Can visitors park on campus for free?", Topic.TRANSPORTATION_PARKING),
    TopicCase("Do I need health insurance as a student?", Topic.HEALTH_WELLNESS),
    TopicCase("How do I waive the student health insurance plan?", Topic.HEALTH_WELLNESS),
    TopicCase("What does the Student Health Insurance Plan cover?", Topic.HEALTH_WELLNESS),
    TopicCase(
        "Where do I go for a doctor's appointment on campus?",
        Topic.HEALTH_WELLNESS,
        xfail_reason=(
            "loses to DINING -- documented, long-known residual (see topic_classifier.py) "
            "[currently: transportation, 0.654]"
        ),
    ),
    TopicCase(
        "Are international students required to have health insurance?",
        Topic.HEALTH_WELLNESS,
        xfail_reason=(
            "migration to Source Manifest V2 taxonomy: loses to FINANCIAL_AID_SCHOLARSHIPS "
            "[currently: financial_aid_scholarships, 0.765]"
        ),
    ),
    TopicCase("Can I opt out of the mandatory health insurance?", Topic.HEALTH_WELLNESS),
    TopicCase("Where's the closest place to see a doctor as a student?", Topic.HEALTH_WELLNESS),
    TopicCase("Does UIUC offer graduate student health insurance?", Topic.HEALTH_WELLNESS),
    TopicCase(
        "What's covered under the mandatory Student Health Insurance Plan?",
        Topic.HEALTH_WELLNESS,
    ),
    TopicCase(
        "Can I stay on my parents' health insurance instead of the university plan?",
        Topic.HEALTH_WELLNESS,
    ),
    TopicCase("Does the student health plan cover prescriptions?", Topic.HEALTH_WELLNESS),
    TopicCase(
        "What's the deadline to waive student health insurance?",
        Topic.HEALTH_WELLNESS,
        xfail_reason=(
            "migration to Source Manifest V2 taxonomy: loses to FINANCIAL_AID_SCHOLARSHIPS "
            "[currently: financial_aid_scholarships, 0.705]"
        ),
    ),
    TopicCase("Is McKinley Health Center free to use?", Topic.HEALTH_WELLNESS),
    TopicCase("Where can I get a flu shot on campus?", Topic.HEALTH_WELLNESS),
    TopicCase("Does the health center offer mental health counseling?", Topic.HEALTH_WELLNESS),
    # Both real live failures (150-question sweep, confirmed via /retrieve): dead-ended the same
    # way the ARC bug did before the dedicated exemplars above were added.
    TopicCase("Is McKinley open on weekends?", Topic.HEALTH_WELLNESS),
    TopicCase("Is counseling covered by my health fee?", Topic.HEALTH_WELLNESS),
    TopicCase("How do I get a gym membership?", Topic.CAMPUS_RECREATION),
    TopicCase("What fitness facilities are available on campus?", Topic.CAMPUS_RECREATION),
    TopicCase("Can I join intramural sports?", Topic.CAMPUS_RECREATION),
    TopicCase("Does the campus have a swimming pool?", Topic.CAMPUS_RECREATION),
    TopicCase("Is the recreation center free for students?", Topic.CAMPUS_RECREATION),
    TopicCase("Is the climbing wall open to all students?", Topic.CAMPUS_RECREATION),
    TopicCase("What intramural sports are offered each semester?", Topic.CAMPUS_RECREATION),
    TopicCase("Can I rent kayaks or camping gear from the rec center?", Topic.CAMPUS_RECREATION),
    TopicCase(
        "Are group fitness classes included with my rec center membership?",
        Topic.CAMPUS_RECREATION,
    ),
    TopicCase("Does the ARC have a rock climbing wall?", Topic.CAMPUS_RECREATION),
    # Real live failure (confirmed via /api/v1/chat): classified as
    # STUDENT_ORGANIZATIONS_ENGAGEMENT (0.617) over CAMPUS_RECREATION (0.544) before the
    # dedicated exemplar above was added -- retrieval then filtered to a full page of wrong-topic
    # chunks, all scoring below min_rerank_score, producing a false "couldn't find anything" for
    # a question the corpus actually answers.
    TopicCase("How do I get a membership to the ARC?", Topic.CAMPUS_RECREATION),
    # Both real live failures (150-question sweep, confirmed via /retrieve): dead-ended the same
    # way the ARC bug above did before the dedicated exemplars above were added.
    TopicCase("What's the difference between the ARC and CRCE?", Topic.CAMPUS_RECREATION),
    TopicCase("Can I rent a kayak from campus rec?", Topic.CAMPUS_RECREATION),
    # Real live failure (150-question sweep round 2, confirmed via /retrieve): dead-ended the same
    # way the ARC bug did before the dedicated exemplar above was added.
    TopicCase("Is CRCE open on weekends?", Topic.CAMPUS_RECREATION),
    TopicCase("How do I register a new student organization?", Topic.STUDENT_ORGANIZATIONS_ENGAGEMENT),
    TopicCase("How many student organizations are there at UIUC?", Topic.STUDENT_ORGANIZATIONS_ENGAGEMENT),
    TopicCase("How do I join a student club?", Topic.STUDENT_ORGANIZATIONS_ENGAGEMENT),
    TopicCase(
        "What is the process for starting a registered student organization?",
        Topic.STUDENT_ORGANIZATIONS_ENGAGEMENT,
    ),
    TopicCase(
        "How do I find student organizations related to my major?",
        Topic.STUDENT_ORGANIZATIONS_ENGAGEMENT,
    ),
    TopicCase("How do I start a new club on campus?", Topic.STUDENT_ORGANIZATIONS_ENGAGEMENT),
    TopicCase(
        "How do I find a list of registered student organizations?",
        Topic.STUDENT_ORGANIZATIONS_ENGAGEMENT,
    ),
    TopicCase(
        "What's required to keep a student organization active each year?",
        Topic.STUDENT_ORGANIZATIONS_ENGAGEMENT,
    ),
    TopicCase("Can graduate students start a student organization?", Topic.STUDENT_ORGANIZATIONS_ENGAGEMENT),
    TopicCase("How do I get involved in student government?", Topic.STUDENT_ORGANIZATIONS_ENGAGEMENT),
    # Real live failure (150-question sweep round 2, confirmed via /retrieve): dead-ended the same
    # way the ARC bug did before the dedicated exemplar above was added.
    TopicCase("How do I sign up to be an orientation leader?", Topic.ORIENTATION_NEW_STUDENTS),
    # Both real live failures (150-question sweep, confirmed via /retrieve): dead-ended the same
    # way the ARC bug did before the dedicated exemplars above were added.
    TopicCase("How do I join an RSO?", Topic.STUDENT_ORGANIZATIONS_ENGAGEMENT),
    TopicCase("What are the rules for tabling on the quad?", Topic.STUDENT_ORGANIZATIONS_ENGAGEMENT),
    TopicCase("When does the fall semester start?", Topic.ACADEMIC_CALENDAR_GRADUATION),
    TopicCase("What is the add/drop deadline?", Topic.ACADEMIC_CALENDAR_GRADUATION),
    TopicCase("When is fall break?", Topic.ACADEMIC_CALENDAR_GRADUATION),
    TopicCase("When does the spring semester end?", Topic.ACADEMIC_CALENDAR_GRADUATION),
    TopicCase("What are the final exam dates?", Topic.ACADEMIC_CALENDAR_GRADUATION),
    TopicCase("When do finals start this semester?", Topic.ACADEMIC_CALENDAR_GRADUATION),
    TopicCase("When does winter break start and end?", Topic.ACADEMIC_CALENDAR_GRADUATION),
    TopicCase("What's the last day of finals week?", Topic.ACADEMIC_CALENDAR_GRADUATION),
    TopicCase("Is there a reading day before finals?", Topic.ACADEMIC_CALENDAR_GRADUATION),
    TopicCase("When do grades get posted after finals?", Topic.ACADEMIC_CALENDAR_GRADUATION),
    TopicCase("How do I register for classes?", Topic.REGISTRATION_RECORDS),
    TopicCase("Where can I find the course catalog?", Topic.CAMPUS_SERVICES_FACILITIES),
    TopicCase("How do I drop a class?", Topic.REGISTRATION_RECORDS),
    TopicCase("What's the last day to drop a class without a W?", Topic.REGISTRATION_RECORDS),
    TopicCase("How do I use the course explorer to plan my schedule?", Topic.ACADEMICS),
    TopicCase("How many times can I retake a failed course?", Topic.ACADEMICS),
    TopicCase(
        "What's the penalty for a late add/drop request?",
        Topic.REGISTRATION_RECORDS,
        xfail_reason=(
            "migration to Source Manifest V2 taxonomy: loses to ACADEMIC_CALENDAR_GRADUATION "
            "[currently: academic_calendar_graduation, 0.801]"
        ),
    ),
    TopicCase("Can I audit a class without getting credit?", Topic.ACADEMICS),
    TopicCase("Can I place a hold on my own account voluntarily?", Topic.REGISTRATION_RECORDS),
    # Three real live failures (150-question sweep, confirmed via /retrieve): dead-ended the same
    # way the ARC bug did before the dedicated exemplars above were added.
    TopicCase("What do I do if I have a hold on my account?", Topic.REGISTRATION_RECORDS),
    TopicCase("How do I change my legal name in the system?", Topic.REGISTRATION_RECORDS),
    TopicCase("Can my parents see my grades?", Topic.REGISTRATION_RECORDS),
    TopicCase("How do I contact campus police?", Topic.CAMPUS_SAFETY),
    TopicCase("Is there a safety escort service on campus?", Topic.CAMPUS_SAFETY),
    TopicCase("How do I report a crime on campus?", Topic.CAMPUS_SAFETY),
    TopicCase("What emergency alert system does UIUC use?", Topic.CAMPUS_SAFETY),
    TopicCase("Who do I call if I feel unsafe walking at night on campus?", Topic.CAMPUS_SAFETY),
    TopicCase("What number do I call for a campus safety escort at night?", Topic.CAMPUS_SAFETY),
    TopicCase("Does UIUC have blue-light emergency phones on campus?", Topic.CAMPUS_SAFETY),
    TopicCase("How do I sign up for Illini-Alert emergency notifications?", Topic.CAMPUS_SAFETY),
    TopicCase("How do I apply for disability accommodations?", Topic.ACCESSIBILITY_DISABILITY_SUPPORT),
    TopicCase("What documentation do I need for accommodations?", Topic.ACCESSIBILITY_DISABILITY_SUPPORT),
    TopicCase("What is DRES?", Topic.ACCESSIBILITY_DISABILITY_SUPPORT),
    TopicCase("Can I get extended time on exams for a disability?", Topic.ACCESSIBILITY_DISABILITY_SUPPORT),
    TopicCase("How do I request accommodations for ADHD?", Topic.ACCESSIBILITY_DISABILITY_SUPPORT),
    TopicCase("What accommodations does DRES provide for testing?", Topic.ACCESSIBILITY_DISABILITY_SUPPORT),
    TopicCase("Can DRES help with accessible campus housing?", Topic.ACCESSIBILITY_DISABILITY_SUPPORT),
    TopicCase("Do I need a doctor's note to register with DRES?", Topic.ACCESSIBILITY_DISABILITY_SUPPORT),
    # Both real live failures (150-question sweep, confirmed via /retrieve): dead-ended the same
    # way the ARC bug did before the dedicated exemplars above were added.
    TopicCase("How do I get extra time on exams?", Topic.ACCESSIBILITY_DISABILITY_SUPPORT),
    TopicCase("Can I rent a wheelchair from campus?", Topic.ACCESSIBILITY_DISABILITY_SUPPORT),
    # Also a real live failure, but every exemplar wording tried in topic_classifier.py either
    # failed to beat TRANSPORTATION_PARKING's own strong pull for this exact phrasing or caused
    # new regressions on plain parking queries -- documented residual, not silently dropped.
    TopicCase(
        "Is there accessible parking near the dorms?",
        Topic.ACCESSIBILITY_DISABILITY_SUPPORT,
        xfail_reason=(
            "150-question sweep: loses to TRANSPORTATION_PARKING "
            "[currently: transportation_parking, 0.725]"
        ),
    ),
    TopicCase("What career services does UIUC offer?", Topic.CAREER_EMPLOYMENT),
    TopicCase(
        "How do I get my resume reviewed?",
        Topic.CAREER_EMPLOYMENT,
        xfail_reason=(
            "migration to Source Manifest V2 taxonomy: loses to ADMISSIONS "
            "[currently: admissions, 0.627]"
        ),
    ),
    TopicCase("Does the Career Center help with job searching?", Topic.CAREER_EMPLOYMENT),
    TopicCase("How do I sign up for career coaching?", Topic.CAREER_EMPLOYMENT),
    TopicCase("Does the Career Center help with salary negotiation?", Topic.CAREER_EMPLOYMENT),
    TopicCase("Can the Career Center help me practice for interviews?", Topic.CAREER_EMPLOYMENT),
    TopicCase("Does the Career Center offer mock interviews?", Topic.CAREER_EMPLOYMENT),
    TopicCase(
        "Does the Career Center have resources for graduate students on the job market?",
        Topic.CAREER_EMPLOYMENT,
    ),
    TopicCase(
        "How do I sign up for on-campus recruiting through the Career Center?",
        Topic.CAREER_EMPLOYMENT,
    ),
    TopicCase("How do I contact my academic advisor?", Topic.ACADEMIC_ADVISING),
    TopicCase("Where is the academic advising office?", Topic.ACADEMIC_ADVISING),
    TopicCase("Do I need to meet with my advisor before registering?", Topic.ACADEMIC_ADVISING),
    TopicCase("How do I change my major?", Topic.ACADEMIC_ADVISING),
    TopicCase("How often should I meet with my academic advisor?", Topic.ACADEMIC_ADVISING),
    TopicCase("Can my academic advisor help me pick a minor?", Topic.ACADEMIC_ADVISING),
    TopicCase(
        "What happens if I miss my advising appointment before registration?",
        Topic.ACADEMIC_ADVISING,
        xfail_reason=(
            "migration to Source Manifest V2 taxonomy: loses to REGISTRATION_RECORDS "
            "[currently: registration_records, 0.679]"
        ),
    ),
    TopicCase("Does the university offer peer tutoring?", Topic.ACADEMIC_ADVISING),
    TopicCase("What are the requirements to declare a major in LAS?", Topic.ACADEMIC_ADVISING),
    TopicCase("asdfghjkl qwerty", None),
    TopicCase(
        "what's the weather like today",
        None,
        xfail_reason=(
            "migration to Source Manifest V2 taxonomy: loses to ACADEMIC_CALENDAR_GRADUATION "
            "[currently: academic_calendar_graduation, 0.559]"
        ),
    ),
    TopicCase("who is the president of the United States", None),
    TopicCase(
        "what time is it right now",
        None,
        xfail_reason=("loses to ACADEMIC_CALENDAR [currently: academic_calendar, 0.575]"),
    ),
    TopicCase(
        "can you recommend a good pizza place",
        None,
        xfail_reason=(
            "loses to DINING -- superficial word overlap on an off-topic request "
            "[currently: dining, 0.557]"
        ),
    ),
    TopicCase(
        "tell me about stuff",
        None,
        xfail_reason=(
            "loses to CAMPUS_SAFETY -- a vague, on-its-face-ambiguous message should "
            "trigger clarification, not a confident wrong guess [currently: housing, "
            "0.571]"
        ),
    ),
    TopicCase("asdlkfj random gibberish text", None),
    TopicCase("do you have feelings", None),
    TopicCase(
        "What mental health resources are available to students?",
        None,
        xfail_reason=(
            "loses to ACCESSIBILITY -- there is deliberately no dedicated "
            "counseling/mental-health topic (see topic_classifier.py's corpus-hygiene "
            "history), so this should fall to clarification, not a confident wrong guess "
            "[currently: housing, 0.624]"
        ),
    ),
)
