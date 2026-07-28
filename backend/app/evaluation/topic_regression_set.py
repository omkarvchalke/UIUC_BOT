"""306-case topic-classification regression set: for every case, the
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
comments on Topic.TRANSPORTATION, Topic.REGISTRATION, the
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
off-topic message -- fixing those needs a different mechanism entirely
(e.g. a margin/runner-up check, not just more vectors).

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
    ),
    TopicCase("What documents do I need to complete my graduate application?", Topic.ADMISSIONS),
    TopicCase("Can I apply as a second bachelor's degree student?", Topic.ADMISSIONS),
    TopicCase("What's the acceptance rate for freshman applicants?", Topic.ADMISSIONS),
    TopicCase("Is UIUC test-optional for admissions?", Topic.ADMISSIONS),
    TopicCase("Can I transfer in with an associate's degree?", Topic.ADMISSIONS),
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
    TopicCase("How do I register as a new student?", Topic.REGISTRATION),
    TopicCase("What is New Student Registration?", Topic.REGISTRATION),
    TopicCase("When can continuing students register for classes?", Topic.COURSE_REGISTRATION),
    TopicCase("How do I register for New Student Registration as a transfer?", Topic.REGISTRATION),
    TopicCase("Do I need to complete registration before orientation?", Topic.REGISTRATION),
    TopicCase("What happens during New Student Registration?", Topic.REGISTRATION),
    TopicCase("Is New Student Registration mandatory?", Topic.REGISTRATION),
    TopicCase("How do I check my registration appointment time?", Topic.COURSE_REGISTRATION),
    TopicCase(
        "Do continuing students need to register every semester?",
        Topic.COURSE_REGISTRATION,
    ),
    TopicCase(
        "What's the difference between new student registration and regular registration?",
        Topic.REGISTRATION,
    ),
    TopicCase("Is there a fee for New Student Registration?", Topic.REGISTRATION),
    TopicCase(
        "Can I skip New Student Registration if I've already registered for classes?",
        Topic.REGISTRATION,
        xfail_reason=(
            "loses to COURSE_REGISTRATION -- a compound query naming both senses of "
            "'register' in one sentence, a known hard case for a single-topic classifier "
            "[currently: course_registration, 0.767]"
        ),
    ),
    TopicCase("How do I get a letter confirming my enrollment status?", Topic.REGISTRATION),
    TopicCase(
        "Where do continuing students go to check their registration time slot?",
        Topic.REGISTRATION,
    ),
    TopicCase("Do I have to sign up for NSR before I move in?", Topic.REGISTRATION),
    TopicCase("What is the process for requesting a leave of absence?", Topic.REGISTRATION),
    TopicCase("What is Welcome Week?", Topic.ORIENTATION),
    TopicCase("Is orientation mandatory for freshmen?", Topic.ORIENTATION),
    TopicCase("What happens at international student orientation?", Topic.ORIENTATION),
    TopicCase("When is orientation for transfer students?", Topic.ORIENTATION),
    TopicCase("What should I bring to orientation?", Topic.ORIENTATION),
    TopicCase("Can my parents attend orientation with me?", Topic.ORIENTATION),
    TopicCase("How long does orientation last?", Topic.ORIENTATION),
    TopicCase("Do graduate students have an orientation?", Topic.ORIENTATION),
    TopicCase("What's Welcome Week actually like?", Topic.ORIENTATION),
    TopicCase("Is there a virtual orientation option?", Topic.ORIENTATION),
    TopicCase("What topics are covered during Welcome Week programming?", Topic.ORIENTATION),
    TopicCase(
        "Do I need to attend orientation before I can register for classes?",
        Topic.ORIENTATION,
        xfail_reason=(
            "loses to COURSE_REGISTRATION -- 'register for classes' phrase dominates "
            "[currently: course_registration, 0.792]"
        ),
    ),
    TopicCase("What happens if I miss my orientation session?", Topic.ORIENTATION),
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
    TopicCase("What happens to unused Dining Dollars at the end of the year?", Topic.DINING),
    TopicCase("What's included in Dining Dollars?", Topic.DINING),
    TopicCase("What's the cost of an on-campus meal plan per semester?", Topic.DINING),
    TopicCase("Are there gluten-free options in the dining halls?", Topic.DINING),
    TopicCase("Can I get food delivered to my dorm through the meal plan?", Topic.DINING),
    TopicCase("Are there halal or kosher dining options?", Topic.DINING),
    TopicCase("What's the meal plan cancellation policy?", Topic.DINING),
    TopicCase("How do dining dollars roll over between semesters?", Topic.DINING),
    TopicCase("How much is out-of-state tuition?", Topic.FINANCIAL_AID),
    TopicCase("How do I apply for financial aid?", Topic.FINANCIAL_AID),
    TopicCase("What is the FAFSA deadline?", Topic.FINANCIAL_AID),
    TopicCase("What types of financial aid does UIUC offer?", Topic.FINANCIAL_AID),
    TopicCase("How do I pay my tuition bill?", Topic.FINANCIAL_AID),
    TopicCase("What is the Illinois Commitment program?", Topic.FINANCIAL_AID),
    TopicCase("Are there refund options for overpayment?", Topic.FINANCIAL_AID),
    TopicCase("What banking options are available through the i-card?", Topic.FINANCIAL_AID),
    TopicCase("What is the average cost of textbooks?", Topic.FINANCIAL_AID),
    TopicCase("Where do I buy textbooks?", Topic.FINANCIAL_AID),
    TopicCase("Can I get a refund if I overpay my tuition bill?", Topic.FINANCIAL_AID),
    TopicCase("What's the Illinois Commitment and am I eligible?", Topic.FINANCIAL_AID),
    TopicCase("How much financial aid will I get?", Topic.FINANCIAL_AID),
    TopicCase("What is the net price calculator?", Topic.FINANCIAL_AID),
    TopicCase(
        "How do I check my financial aid award status?",
        Topic.FINANCIAL_AID,
        xfail_reason=("loses to SCHOLARSHIPS [currently: scholarships, 0.691]"),
    ),
    TopicCase("Are there payment plans for tuition?", Topic.FINANCIAL_AID),
    TopicCase("What's a Pell Grant?", Topic.FINANCIAL_AID),
    TopicCase(
        "Do international students qualify for financial aid?",
        Topic.FINANCIAL_AID,
        xfail_reason=(
            "loses to INTERNATIONAL_STUDENT_SERVICES [currently: "
            "international_student_services, 0.660]"
        ),
    ),
    TopicCase("Is the Illinois Commitment scholarship need-based?", Topic.FINANCIAL_AID),
    TopicCase("Can I get a tuition waiver as a graduate assistant?", Topic.FINANCIAL_AID),
    TopicCase("What scholarships are available for incoming freshmen?", Topic.SCHOLARSHIPS),
    TopicCase(
        "Do I need to submit a separate application for merit scholarships?",
        Topic.SCHOLARSHIPS,
    ),
    TopicCase("Are there scholarships for transfer students?", Topic.SCHOLARSHIPS),
    TopicCase("What is the deadline to apply for scholarships?", Topic.SCHOLARSHIPS),
    TopicCase("Are scholarships renewable each year?", Topic.SCHOLARSHIPS),
    TopicCase("Where can I find a list of available scholarships?", Topic.SCHOLARSHIPS),
    TopicCase("Is there a merit scholarship I should apply for separately?", Topic.SCHOLARSHIPS),
    TopicCase("Can I combine multiple scholarships?", Topic.SCHOLARSHIPS),
    TopicCase("Do departmental scholarships require a separate application?", Topic.SCHOLARSHIPS),
    TopicCase("How do I find an on-campus job?", Topic.STUDENT_EMPLOYMENT),
    TopicCase("What is work study?", Topic.STUDENT_EMPLOYMENT),
    TopicCase("Can international students work on campus?", Topic.STUDENT_EMPLOYMENT),
    TopicCase("How many hours can I work as a student employee?", Topic.STUDENT_EMPLOYMENT),
    TopicCase("Where do I search for campus jobs?", Topic.STUDENT_EMPLOYMENT),
    TopicCase("What is Hire Illini?", Topic.STUDENT_EMPLOYMENT),
    TopicCase("Where do I look for part-time jobs on campus?", Topic.STUDENT_EMPLOYMENT),
    TopicCase(
        "What's the maximum number of hours a work-study student can work?",
        Topic.STUDENT_EMPLOYMENT,
    ),
    TopicCase("Can I have more than one on-campus job at a time?", Topic.STUDENT_EMPLOYMENT),
    TopicCase("How do I apply for a graduate assistantship?", Topic.STUDENT_EMPLOYMENT),
    TopicCase("Does working on campus affect my financial aid?", Topic.STUDENT_EMPLOYMENT),
    TopicCase(
        "What's the difference between a graduate assistantship and work study?",
        Topic.STUDENT_EMPLOYMENT,
    ),
    TopicCase(
        "What services does ISSS provide for international students?",
        Topic.INTERNATIONAL_STUDENT_SERVICES,
    ),
    TopicCase(
        "Who do I contact for international student support?",
        Topic.INTERNATIONAL_STUDENT_SERVICES,
    ),
    TopicCase(
        "What resources are available for international students on campus?",
        Topic.INTERNATIONAL_STUDENT_SERVICES,
    ),
    TopicCase(
        "What should international students do before they arrive on campus?",
        Topic.INTERNATIONAL_STUDENT_SERVICES,
    ),
    TopicCase(
        "What documents should I bring when I first arrive at UIUC?",
        Topic.INTERNATIONAL_STUDENT_SERVICES,
        xfail_reason=("loses to ADMISSIONS [currently: admissions, 0.766]"),
    ),
    TopicCase(
        "What does ISSS stand for and what do they do?",
        Topic.INTERNATIONAL_STUDENT_SERVICES,
    ),
    TopicCase("Does ISSS help with cultural adjustment?", Topic.INTERNATIONAL_STUDENT_SERVICES),
    TopicCase(
        "How do I get a letter from ISSS for a bank account?",
        Topic.INTERNATIONAL_STUDENT_SERVICES,
    ),
    TopicCase("What is a Form I-20?", Topic.VISA),
    TopicCase("How do I maintain my F-1 visa status?", Topic.VISA),
    TopicCase("What documents do I need for my visa interview?", Topic.VISA),
    TopicCase("What happens if my I-20 has an error?", Topic.VISA),
    TopicCase("How long is my visa valid while I'm a student?", Topic.VISA),
    TopicCase("My I-20 has a typo, what do I do?", Topic.VISA),
    TopicCase("How do I renew my F-1 visa?", Topic.VISA),
    TopicCase("What is SEVIS and why does it matter?", Topic.VISA),
    TopicCase("Can I travel outside the US and come back on my visa?", Topic.VISA),
    TopicCase("Does my visa expire if I stay in the US past my program end date?", Topic.VISA),
    TopicCase("What is Curricular Practical Training?", Topic.CPT),
    TopicCase("How do I apply for CPT?", Topic.CPT),
    TopicCase("Do I need my academic advisor's approval for CPT?", Topic.CPT),
    TopicCase("Can I do CPT during my first year?", Topic.CPT),
    TopicCase("Can I start CPT my first semester?", Topic.CPT),
    TopicCase("How many hours of CPT can I do without affecting my OPT eligibility?", Topic.CPT),
    TopicCase("Does CPT require a job offer before applying?", Topic.CPT),
    TopicCase("Is CPT authorization tied to a specific employer?", Topic.CPT),
    TopicCase("How do I apply for OPT?", Topic.OPT),
    TopicCase("What is Optional Practical Training?", Topic.OPT),
    TopicCase("When can graduate students apply for OPT?", Topic.OPT),
    TopicCase("How long does OPT last after graduation?", Topic.OPT),
    TopicCase("What is the OPT filing address?", Topic.OPT),
    TopicCase("Do grad students apply for OPT differently than undergrads?", Topic.OPT),
    TopicCase("What is STEM OPT extension?", Topic.OPT),
    TopicCase("How soon after graduation do I need to apply for OPT?", Topic.OPT),
    TopicCase("Can I travel internationally while my OPT application is pending?", Topic.OPT),
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
    TopicCase("How do I get from O'Hare Airport to UIUC without a car?", Topic.TRANSPORTATION),
    TopicCase("What is the cheapest way to get to campus from Chicago?", Topic.TRANSPORTATION),
    TopicCase("How much does an MTD bus pass cost?", Topic.TRANSPORTATION),
    TopicCase("How do I get a parking permit?", Topic.TRANSPORTATION),
    TopicCase("What are the parking rates on campus?", Topic.TRANSPORTATION),
    TopicCase("Does UIUC have its own airport?", Topic.TRANSPORTATION),
    TopicCase("Is the bus free for students?", Topic.TRANSPORTATION),
    TopicCase("How do I track the campus bus in real time?", Topic.TRANSPORTATION),
    TopicCase("Can I bring a car to campus as a freshman?", Topic.TRANSPORTATION),
    TopicCase("How do I get from Willard Airport to campus?", Topic.TRANSPORTATION),
    TopicCase("How do I renew my parking permit?", Topic.TRANSPORTATION),
    TopicCase("Does UIUC have a shuttle to the airport?", Topic.TRANSPORTATION),
    TopicCase("What's the process to appeal a parking ticket?", Topic.TRANSPORTATION),
    TopicCase("Is there a night bus service on campus?", Topic.TRANSPORTATION),
    TopicCase("How do I appeal a parking citation?", Topic.TRANSPORTATION),
    TopicCase("What's the fastest way from Midway Airport to campus?", Topic.TRANSPORTATION),
    TopicCase("Is there a campus map showing bus routes?", Topic.TRANSPORTATION),
    TopicCase("What's the closest airport to Champaign-Urbana?", Topic.TRANSPORTATION),
    TopicCase("Is the campus bus system free with my student ID?", Topic.TRANSPORTATION),
    TopicCase("How do I renew a parking permit that's about to expire?", Topic.TRANSPORTATION),
    TopicCase("Do I need a car as a UIUC student?", Topic.TRANSPORTATION),
    TopicCase("Does UIUC have a bike share program?", Topic.TRANSPORTATION),
    TopicCase("How do I get a Zipcar or campus car-share membership?", Topic.TRANSPORTATION),
    TopicCase("Do I need health insurance as a student?", Topic.HEALTH_INSURANCE),
    TopicCase("How do I waive the student health insurance plan?", Topic.HEALTH_INSURANCE),
    TopicCase("What does the Student Health Insurance Plan cover?", Topic.HEALTH_INSURANCE),
    TopicCase(
        "Where do I go for a doctor's appointment on campus?",
        Topic.HEALTH_INSURANCE,
        xfail_reason=(
            "loses to DINING -- documented, long-known residual (see topic_classifier.py) "
            "[currently: transportation, 0.654]"
        ),
    ),
    TopicCase(
        "Are international students required to have health insurance?",
        Topic.HEALTH_INSURANCE,
    ),
    TopicCase("Can I opt out of the mandatory health insurance?", Topic.HEALTH_INSURANCE),
    TopicCase("Where's the closest place to see a doctor as a student?", Topic.HEALTH_INSURANCE),
    TopicCase("Does UIUC offer graduate student health insurance?", Topic.HEALTH_INSURANCE),
    TopicCase(
        "What's covered under the mandatory Student Health Insurance Plan?",
        Topic.HEALTH_INSURANCE,
    ),
    TopicCase(
        "Can I stay on my parents' health insurance instead of the university plan?",
        Topic.HEALTH_INSURANCE,
    ),
    TopicCase("Does the student health plan cover prescriptions?", Topic.HEALTH_INSURANCE),
    TopicCase("What's the deadline to waive student health insurance?", Topic.HEALTH_INSURANCE),
    TopicCase("Is McKinley Health Center free to use?", Topic.HEALTH_INSURANCE),
    TopicCase("Where can I get a flu shot on campus?", Topic.HEALTH_INSURANCE),
    TopicCase("Does the health center offer mental health counseling?", Topic.HEALTH_INSURANCE),
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
    TopicCase("How do I register a new student organization?", Topic.STUDENT_ORGANIZATIONS),
    TopicCase("How many student organizations are there at UIUC?", Topic.STUDENT_ORGANIZATIONS),
    TopicCase("How do I join a student club?", Topic.STUDENT_ORGANIZATIONS),
    TopicCase(
        "What is the process for starting a registered student organization?",
        Topic.STUDENT_ORGANIZATIONS,
    ),
    TopicCase(
        "How do I find student organizations related to my major?",
        Topic.STUDENT_ORGANIZATIONS,
    ),
    TopicCase("How do I start a new club on campus?", Topic.STUDENT_ORGANIZATIONS),
    TopicCase(
        "How do I find a list of registered student organizations?",
        Topic.STUDENT_ORGANIZATIONS,
    ),
    TopicCase(
        "What's required to keep a student organization active each year?",
        Topic.STUDENT_ORGANIZATIONS,
    ),
    TopicCase("Can graduate students start a student organization?", Topic.STUDENT_ORGANIZATIONS),
    TopicCase("How do I get involved in student government?", Topic.STUDENT_ORGANIZATIONS),
    TopicCase("When does the fall semester start?", Topic.ACADEMIC_CALENDAR),
    TopicCase("What is the add/drop deadline?", Topic.ACADEMIC_CALENDAR),
    TopicCase("When is fall break?", Topic.ACADEMIC_CALENDAR),
    TopicCase("When does the spring semester end?", Topic.ACADEMIC_CALENDAR),
    TopicCase("What are the final exam dates?", Topic.ACADEMIC_CALENDAR),
    TopicCase("When do finals start this semester?", Topic.ACADEMIC_CALENDAR),
    TopicCase("When does winter break start and end?", Topic.ACADEMIC_CALENDAR),
    TopicCase("What's the last day of finals week?", Topic.ACADEMIC_CALENDAR),
    TopicCase("Is there a reading day before finals?", Topic.ACADEMIC_CALENDAR),
    TopicCase("When do grades get posted after finals?", Topic.ACADEMIC_CALENDAR),
    TopicCase("How do I register for classes?", Topic.COURSE_REGISTRATION),
    TopicCase("Where can I find the course catalog?", Topic.COURSE_REGISTRATION),
    TopicCase("How do I drop a class?", Topic.COURSE_REGISTRATION),
    TopicCase("What's the last day to drop a class without a W?", Topic.COURSE_REGISTRATION),
    TopicCase("How do I use the course explorer to plan my schedule?", Topic.COURSE_REGISTRATION),
    TopicCase("How many times can I retake a failed course?", Topic.COURSE_REGISTRATION),
    TopicCase("What's the penalty for a late add/drop request?", Topic.COURSE_REGISTRATION),
    TopicCase("Can I audit a class without getting credit?", Topic.COURSE_REGISTRATION),
    TopicCase("Can I place a hold on my own account voluntarily?", Topic.COURSE_REGISTRATION),
    TopicCase("How do I contact campus police?", Topic.CAMPUS_SAFETY),
    TopicCase("Is there a safety escort service on campus?", Topic.CAMPUS_SAFETY),
    TopicCase("How do I report a crime on campus?", Topic.CAMPUS_SAFETY),
    TopicCase("What emergency alert system does UIUC use?", Topic.CAMPUS_SAFETY),
    TopicCase("Who do I call if I feel unsafe walking at night on campus?", Topic.CAMPUS_SAFETY),
    TopicCase("What number do I call for a campus safety escort at night?", Topic.CAMPUS_SAFETY),
    TopicCase("Does UIUC have blue-light emergency phones on campus?", Topic.CAMPUS_SAFETY),
    TopicCase("How do I sign up for Illini-Alert emergency notifications?", Topic.CAMPUS_SAFETY),
    TopicCase("How do I apply for disability accommodations?", Topic.ACCESSIBILITY),
    TopicCase("What documentation do I need for accommodations?", Topic.ACCESSIBILITY),
    TopicCase("What is DRES?", Topic.ACCESSIBILITY),
    TopicCase("Can I get extended time on exams for a disability?", Topic.ACCESSIBILITY),
    TopicCase("How do I request accommodations for ADHD?", Topic.ACCESSIBILITY),
    TopicCase("What accommodations does DRES provide for testing?", Topic.ACCESSIBILITY),
    TopicCase("Can DRES help with accessible campus housing?", Topic.ACCESSIBILITY),
    TopicCase("Do I need a doctor's note to register with DRES?", Topic.ACCESSIBILITY),
    TopicCase("What career services does UIUC offer?", Topic.CAREER_SERVICES),
    TopicCase("How do I get my resume reviewed?", Topic.CAREER_SERVICES),
    TopicCase("Does the Career Center help with job searching?", Topic.CAREER_SERVICES),
    TopicCase("How do I sign up for career coaching?", Topic.CAREER_SERVICES),
    TopicCase("Does the Career Center help with salary negotiation?", Topic.CAREER_SERVICES),
    TopicCase("Can the Career Center help me practice for interviews?", Topic.CAREER_SERVICES),
    TopicCase("Does the Career Center offer mock interviews?", Topic.CAREER_SERVICES),
    TopicCase(
        "Does the Career Center have resources for graduate students on the job market?",
        Topic.CAREER_SERVICES,
    ),
    TopicCase(
        "How do I sign up for on-campus recruiting through the Career Center?",
        Topic.CAREER_SERVICES,
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
    ),
    TopicCase("Does the university offer peer tutoring?", Topic.ACADEMIC_ADVISING),
    TopicCase("What are the requirements to declare a major in LAS?", Topic.ACADEMIC_ADVISING),
    TopicCase("asdfghjkl qwerty", None),
    TopicCase("what's the weather like today", None),
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
