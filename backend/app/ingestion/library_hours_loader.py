import json
from datetime import UTC, datetime

from app.ingestion.cleaning import clean_text
from app.ingestion.extracted_document import ExtractedDocument


def parse_library_hours(raw_bytes: bytes, *, fallback_title: str = "Library Hours") -> ExtractedDocument:
    """Turns a libdirectory.library.illinois.edu /Api/Unit/{id} response into text.

    The API returns a one-element list for a single-unit lookup. calendar.nextSevenDays is a
    rolling window (today plus the next six days), each with either a list of open/close spans
    or none at all for a closed day -- formatted here as one line per day so it reads the way a
    person would answer "what are the library hours."

    Every line repeats "hours" and the unit name, deliberately -- not just once in a header.
    ExtractiveAnswerGenerator (app/graph/generation.py) picks its answer sentence by raw
    query-term overlap within a chunk, one line at a time; a header-then-bare-data-lines layout
    left every actual hours line with zero overlap against a "library hours" query (only the
    header mentioned those words), so the picker always won on the header and dropped every real
    time span. Confirmed live before this fix: the answer read as "Main Library hours for the
    next seven days:" with nothing after it.
    """
    payload = json.loads(raw_bytes)
    unit = payload[0] if isinstance(payload, list) else payload

    name = unit.get("unit_name") or fallback_title
    calendar = unit.get("calendar") or {}
    days = calendar.get("nextSevenDays") or []

    lines = [f"{name} hours for the next seven days:"]
    for day in days:
        label = day.get("day", "")
        date = day.get("date", "")
        spans = day.get("hours") or []
        times = "; ".join(span.get("label", "") for span in spans if span.get("label"))
        if label == "Today":
            # Deliberately the most keyword-dense, distinct line: ExtractiveAnswerGenerator picks
            # one sentence per chunk by raw query-term overlap with the question, and "today" is
            # the day almost every real "library hours" question actually means -- this line
            # needs to reliably outscore the other six on realistic phrasings ("what are the
            # library hours", "is the library open right now", "what time does it close today").
            if times:
                lines.append(f"{name} is open right now and today's hours ({date}) are {times}.")
            else:
                lines.append(f"{name} is closed right now, with no hours open today ({date}).")
        elif times:
            lines.append(f"{name} hours on {label} ({date}): open {times}")
        else:
            lines.append(f"{name} hours on {label} ({date}): closed all day")

    address_parts = [unit.get("street_address"), unit.get("city"), unit.get("state")]
    address = ", ".join(part for part in address_parts if part)
    if address:
        lines.append(f"Address: {address}")
    phone = unit.get("phone_number")
    if phone:
        lines.append(f"Phone: {phone}")

    text = clean_text("\n".join(lines))
    return ExtractedDocument(title=f"{name} Hours", text=text, last_updated=datetime.now(UTC))
