from app.ingestion.cleaning import clean_text


def test_collapses_repeated_spaces_and_tabs() -> None:
    assert clean_text("Hello   \t\tworld") == "Hello world"


def test_collapses_excessive_blank_lines() -> None:
    raw = "Paragraph one.\n\n\n\n\nParagraph two."
    assert clean_text(raw) == "Paragraph one.\n\nParagraph two."


def test_strips_control_characters() -> None:
    raw = "Hello\x00\x0bWorld"
    assert clean_text(raw) == "HelloWorld"


def test_normalizes_windows_and_mac_line_endings() -> None:
    assert clean_text("line one\r\nline two\rline three") == "line one\nline two\nline three"


def test_strips_leading_and_trailing_whitespace() -> None:
    assert clean_text("   \n  Hello World  \n  ") == "Hello World"


def test_empty_input_returns_empty_string() -> None:
    assert clean_text("") == ""
    assert clean_text("   \n\n  ") == ""


def test_preserves_meaningful_single_line_breaks() -> None:
    raw = "Line one\nLine two"
    assert clean_text(raw) == "Line one\nLine two"
