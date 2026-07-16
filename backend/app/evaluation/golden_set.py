from dataclasses import dataclass, field

from app.models.conversation_session import StudentType


@dataclass(frozen=True)
class EvalCase:
    """One question against the real, deployed app plus what a correct
    answer must look like. Deliberately checks properties of the answer
    (grounded, cited, not hedging), not exact wording -- Groq's phrasing
    varies between runs even for the same question, but a real answer to
    "how do I apply" should always cite something and never fall back to
    "follow the process on the website" (the exact bug this golden set
    exists to catch a regression of; see the sources.py "gateway page"
    comments).
    """

    name: str
    message: str
    student_type: StudentType | None = None
    expect_grounded: bool | None = None
    expect_clarification: bool | None = None
    min_citations: int = 0
    # Case-insensitive substrings that, if present, mean the model punted
    # instead of answering -- grounded: true doesn't catch this, since a
    # vague pointer back to the source website is technically "supported"
    # by the citation even though it isn't a real answer.
    forbidden_phrases: tuple[str, ...] = field(default_factory=tuple)
    # Retrieval ground truth for Precision@5/Recall@5/MRR/Context Precision
    # (app/evaluation/retrieval_metrics.py). Empty tuple (the default) means
    # "no retrieval ground truth for this case" -- it's skipped in retrieval-
    # metric aggregation, same as min_citations=0/forbidden_phrases=() are
    # already legitimately empty for many cases (a clarification-triggering
    # case has no "correct retrieved document" to check). Only populated
    # when a specific case's own comments already establish the one correct
    # source page -- never guessed from the source manifest alone.
    expected_relevant_urls: tuple[str, ...] = field(default_factory=tuple)


_VAGUE_POINTER_PHRASES = (
    "outlined on the",
    "follow the process outlined",
    "learn how to apply",
    "visit the website",
    "check the website",
)


GOLDEN_SET: tuple[EvalCase, ...] = (
    EvalCase(
        name="freshman_apply_process",
        message="How do I apply as a freshman?",
        student_type=StudentType.FRESHMAN,
        expect_grounded=True,
        min_citations=1,
        forbidden_phrases=_VAGUE_POINTER_PHRASES,
        expected_relevant_urls=("https://www.admissions.illinois.edu/Apply/Freshman/process",),
    ),
    EvalCase(
        # Not "what GPA do I need" -- the freshman requirements page
        # deliberately doesn't publish a minimum GPA (it points to the
        # class profile's middle-50% range instead), unlike the transfer
        # GPA guidelines page, which does. Asking for a GPA here would
        # correctly come back grounded: false since the source really
        # doesn't have one -- that's not a bug to guard against, so ask
        # about something the source does state.
        name="freshman_requirements",
        message="What high school courses and test scores do freshman applicants need?",
        student_type=StudentType.FRESHMAN,
        expect_grounded=True,
        min_citations=1,
        expected_relevant_urls=("https://www.admissions.illinois.edu/apply/freshman/requirements",),
    ),
    EvalCase(
        name="freshman_housing",
        message="Where do freshmen live on campus?",
        student_type=StudentType.FRESHMAN,
        expect_grounded=True,
        min_citations=1,
    ),
    EvalCase(
        name="meal_plans",
        message="What meal plans are available?",
        student_type=StudentType.FRESHMAN,
        expect_grounded=True,
        min_citations=1,
    ),
    EvalCase(
        name="transfer_apply_process",
        message="How do I apply as a transfer student?",
        student_type=StudentType.TRANSFER,
        expect_grounded=True,
        min_citations=1,
        forbidden_phrases=_VAGUE_POINTER_PHRASES,
    ),
    EvalCase(
        name="transfer_gpa",
        message="What GPA do I need to transfer?",
        student_type=StudentType.TRANSFER,
        expect_grounded=True,
        min_citations=1,
    ),
    EvalCase(
        name="transfer_deadlines",
        message="What are the transfer application deadlines?",
        student_type=StudentType.TRANSFER,
        expect_grounded=True,
        min_citations=1,
    ),
    EvalCase(
        name="graduate_requirements",
        message="What are the minimum requirements for graduate admission?",
        student_type=StudentType.GRADUATE,
        expect_grounded=True,
        min_citations=1,
    ),
    EvalCase(
        name="graduate_application_submission",
        message="What do I need to submit for a graduate application?",
        student_type=StudentType.GRADUATE,
        expect_grounded=True,
        min_citations=1,
        forbidden_phrases=_VAGUE_POINTER_PHRASES,
    ),
    EvalCase(
        name="international_english_proficiency",
        message="Do I need to submit an English proficiency test score?",
        student_type=StudentType.INTERNATIONAL,
        expect_grounded=True,
        min_citations=1,
    ),
    EvalCase(
        name="international_opt",
        message="What is OPT and how does it work?",
        student_type=StudentType.INTERNATIONAL,
        expect_grounded=True,
        min_citations=1,
    ),
    EvalCase(
        name="international_cpt",
        message="What is CPT?",
        student_type=StudentType.INTERNATIONAL,
        expect_grounded=True,
        min_citations=1,
    ),
    EvalCase(
        # student_type is FRESHMAN here purely to get past the deliberate
        # first-turn "what kind of student are you" profile gate
        # (check_student_profile_node fires on every first message with no
        # student_type set, regardless of topic) -- financial aid content
        # itself isn't student-type scoped.
        name="financial_aid_types",
        message="What types of financial aid are available?",
        student_type=StudentType.FRESHMAN,
        expect_grounded=True,
        min_citations=1,
    ),
    EvalCase(
        name="course_registration",
        message="How do I register for classes?",
        student_type=StudentType.FRESHMAN,
        expect_grounded=True,
        min_citations=1,
    ),
    EvalCase(
        # Not "how do I get one" / cost -- the permits page states rates
        # exist under a "Rates" heading but never states the actual dollar
        # amount for a student permit anywhere in the scraped text (the
        # only $ figure on the whole page is an unrelated $250 disability-
        # parking fine); a cost question here would correctly come back
        # ungrounded because the source really doesn't have the number, not
        # because of a retrieval bug. Known gap, not yet fixed -- a real
        # rates page would need to be added as its own source.
        name="parking_permit",
        message="What parking permit options are available to students?",
        student_type=StudentType.FRESHMAN,
        expect_grounded=True,
        min_citations=1,
        expected_relevant_urls=("https://parking.illinois.edu/permits",),
    ),
    EvalCase(
        # student_type is FRESHMAN purely to get past the first-turn
        # profile gate (see financial_aid_types above) -- library content
        # isn't student-type scoped either.
        #
        # Known limitation (see sources.py): library hours are JS-rendered,
        # so the static scrape never captures them. Deliberately doesn't
        # assert expect_grounded or min_citations -- a model correctly
        # declining to cite a source that didn't actually answer the
        # question is legitimate (confirmed: llama-4-scout returns
        # citations: [] here, an earlier model returned a citation anyway;
        # both are defensible, so asserting a specific count would be
        # testing model style, not correctness). What's model-independent
        # is that this is an unambiguous, on-topic question, so it should
        # never trigger a clarification. For the same reason,
        # expected_relevant_urls is deliberately left empty too -- there's
        # no source that actually answers this, so no "correct" retrieval
        # target exists to check against.
        name="library_hours",
        message="What are the library hours?",
        student_type=StudentType.FRESHMAN,
        expect_clarification=False,
    ),
    EvalCase(
        name="greeting",
        message="hi",
        student_type=StudentType.FRESHMAN,
        expect_grounded=True,
        expect_clarification=False,
    ),
    EvalCase(
        name="ambiguous_profile_triggers_clarification",
        message="What housing options are there?",
        student_type=None,
        expect_clarification=True,
    ),
    EvalCase(
        name="off_topic_triggers_clarification_not_hallucination",
        message="What's the capital of France?",
        student_type=StudentType.FRESHMAN,
        expect_clarification=True,
    ),
)
