import re

_MULTI_SPACE = re.compile(r"[ \t\xa0]+")
_MULTI_NEWLINE = re.compile(r"\n{3,}")
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
# A lone space directly before terminal punctuation -- an artifact of
# BeautifulSoup's get_text() inserting a separator where an inline element
# (an icon, an empty anchor, a stripped footnote marker) used to sit between
# a word and the punctuation that was meant to immediately follow it, e.g.
# "...Bulletin Board is a communication tool ." Confirmed live via a
# 326-question sweep (answers citing "communities ." / "Bursar's Office .").
_SPACE_BEFORE_PUNCTUATION = re.compile(r" +([.,;:!?])")


def clean_text(raw: str) -> str:
    """Normalize whitespace and strip control characters from extracted document text.

    Deliberately conservative: only removes noise that extraction introduces
    (stray control chars, collapsed whitespace, excessive blank lines, a
    stray space before punctuation) and never rewrites or truncates actual
    content, since downstream chunks are cited verbatim to users.
    """
    text = _CONTROL_CHARS.sub("", raw)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # \xa0 (non-breaking space, from HTML &nbsp; entities) is visual spacing,
    # not meaningful content -- collapse it into normal whitespace the same
    # as a run of plain spaces, rather than letting it survive as a literal
    # \xa0 character in cited answer text. Confirmed live via the same sweep
    # (e.g. "your new\xa0accommodation request").
    lines = [_MULTI_SPACE.sub(" ", line).strip() for line in text.split("\n")]
    text = "\n".join(lines)
    text = _MULTI_NEWLINE.sub("\n\n", text)
    text = _SPACE_BEFORE_PUNCTUATION.sub(r"\1", text)
    return text.strip()
