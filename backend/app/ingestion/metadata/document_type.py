"""Rule-based DocumentType classification: URL-path and title/body keyword
signals, the same style as crawler._infer_student_types -- no LLM call,
deterministic, and unit-testable with no model involved."""

import re

from app.models.document import DocumentType

_URL_PATH_RULES: tuple[tuple[str, DocumentType], ...] = (
    ("/faq", DocumentType.FAQ),
    ("/frequently-asked", DocumentType.FAQ),
    ("/polic", DocumentType.POLICY),  # matches /policy and /policies
    ("/deadline", DocumentType.DEADLINE_REFERENCE),
    ("/dates", DocumentType.DEADLINE_REFERENCE),
    ("/calendar", DocumentType.DEADLINE_REFERENCE),
    ("/news", DocumentType.NEWS_ANNOUNCEMENT),
    ("/events", DocumentType.NEWS_ANNOUNCEMENT),
    ("/announcement", DocumentType.NEWS_ANNOUNCEMENT),
    ("/contact", DocumentType.CONTACT_INFO),
    ("/form", DocumentType.FORM),
    ("/apply", DocumentType.HOW_TO_GUIDE),
    ("/how-to", DocumentType.HOW_TO_GUIDE),
    ("/steps", DocumentType.HOW_TO_GUIDE),
)

_TITLE_KEYWORD_RULES: tuple[tuple[str, DocumentType], ...] = (
    ("faq", DocumentType.FAQ),
    ("frequently asked", DocumentType.FAQ),
    ("policy", DocumentType.POLICY),
    ("policies", DocumentType.POLICY),
    ("deadline", DocumentType.DEADLINE_REFERENCE),
    ("news", DocumentType.NEWS_ANNOUNCEMENT),
    ("contact", DocumentType.CONTACT_INFO),
    ("form", DocumentType.FORM),
    ("application", DocumentType.FORM),
    ("how to", DocumentType.HOW_TO_GUIDE),
    ("steps to", DocumentType.HOW_TO_GUIDE),
)

# Body-text fallback threshold: a page structured as question/answer pairs
# reads like an FAQ even when neither the URL nor title say so explicitly
# (e.g. a page titled just "Housing" laid out as Q&A). Both an absolute
# floor and a density check, so a long page that merely asks a few
# rhetorical questions doesn't trip this.
_FAQ_MIN_QUESTION_MARKS = 5
_FAQ_MIN_QUESTION_MARK_DENSITY = 0.002

# No rule matched: default to the most honest general description --
# "a page describing a UIUC service, program, or requirement" -- rather
# than leaving it unset. Same "best-guess beats blank" philosophy as
# topic classification during crawling (see crawler.py).
_DEFAULT = DocumentType.PROGRAM_DESCRIPTION


def classify_document_type(url: str, title: str, text: str) -> DocumentType:
    lowered_url = url.lower()
    for marker, doc_type in _URL_PATH_RULES:
        if marker in lowered_url:
            return doc_type

    lowered_title = title.lower()
    for keyword, doc_type in _TITLE_KEYWORD_RULES:
        if re.search(rf"\b{re.escape(keyword)}\b", lowered_title):
            return doc_type

    if text:
        question_marks = text.count("?")
        if (
            question_marks >= _FAQ_MIN_QUESTION_MARKS
            and question_marks / len(text) > _FAQ_MIN_QUESTION_MARK_DENSITY
        ):
            return DocumentType.FAQ

    return _DEFAULT
