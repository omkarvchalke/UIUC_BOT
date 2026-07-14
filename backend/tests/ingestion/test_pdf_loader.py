from app.ingestion.pdf_loader import parse_pdf
from tests.ingestion.pdf_helpers import make_pdf_bytes


def test_extracts_text_from_pdf() -> None:
    pdf_bytes = make_pdf_bytes("International students must maintain full-time enrollment.")
    result = parse_pdf(pdf_bytes)
    assert "International students must maintain full-time enrollment." in result.text


def test_extracts_title_from_pdf_metadata() -> None:
    pdf_bytes = make_pdf_bytes("Some content.", title="Sample Form I-20")
    result = parse_pdf(pdf_bytes)
    assert result.title == "Sample Form I-20"


def test_falls_back_to_provided_title_when_pdf_has_none() -> None:
    pdf_bytes = make_pdf_bytes("Some content with no title metadata.")
    result = parse_pdf(pdf_bytes, fallback_title="Manifest Title")
    assert result.title == "Manifest Title"


def test_multi_line_pdf_preserves_all_content() -> None:
    lines = ["Line about CPT.", "Line about OPT.", "Line about the STEM extension."]
    pdf_bytes = make_pdf_bytes("\n".join(lines))
    result = parse_pdf(pdf_bytes)
    for line in lines:
        assert line in result.text
