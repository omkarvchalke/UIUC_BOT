from app.ingestion.metadata.document_type import classify_document_type
from app.models.document import DocumentType


def test_url_path_faq_marker() -> None:
    result = classify_document_type(
        "https://example.illinois.edu/admissions/faq", "Common Questions", "Some text."
    )
    assert result is DocumentType.FAQ


def test_url_path_policy_marker() -> None:
    result = classify_document_type(
        "https://example.illinois.edu/registrar/policies", "Academic Policies", "Some text."
    )
    assert result is DocumentType.POLICY


def test_url_path_deadline_marker() -> None:
    result = classify_document_type(
        "https://example.illinois.edu/registrar/deadlines", "Important Dates", "Some text."
    )
    assert result is DocumentType.DEADLINE_REFERENCE


def test_url_path_wins_over_title_when_both_present() -> None:
    # URL rules are checked first -- deliberately, since the URL is a more
    # stable/curated signal than freeform title text.
    result = classify_document_type("https://example.illinois.edu/faq", "Contact Us", "Some text.")
    assert result is DocumentType.FAQ


def test_title_keyword_when_url_has_no_marker() -> None:
    result = classify_document_type(
        "https://example.illinois.edu/page123", "Financial Aid Policy Overview", "Some text."
    )
    assert result is DocumentType.POLICY


def test_title_form_keyword() -> None:
    result = classify_document_type(
        "https://example.illinois.edu/page", "Housing Application Form", "Some text."
    )
    assert result is DocumentType.FORM


def test_body_text_faq_fallback_when_no_url_or_title_signal() -> None:
    text = " ".join(
        [
            "What is the deadline? When do classes start? Where do I apply?",
            "How much does it cost? Who do I contact? What if I miss it?",
        ]
        * 3
    )
    result = classify_document_type("https://example.illinois.edu/page", "Housing", text)
    assert result is DocumentType.FAQ


def test_falls_back_to_program_description_when_nothing_matches() -> None:
    result = classify_document_type(
        "https://example.illinois.edu/housing/undergraduate",
        "Undergraduate Housing",
        "Freshmen live in university residence halls.",
    )
    assert result is DocumentType.PROGRAM_DESCRIPTION
