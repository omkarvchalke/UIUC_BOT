import json

from app.ingestion.library_hours_loader import parse_library_hours

# Trimmed to the fields the parser actually reads -- a real response from
# libdirectory.library.illinois.edu/Api/Unit/{id} has many more (map URLs, scanner/printer
# links, ...) that aren't relevant to answering "what are the library hours."
_SAMPLE_RESPONSE = [
    {
        "unit_name": "Main Library",
        "street_address": "1408 West Gregory Drive",
        "city": "Urbana",
        "state": "IL",
        "phone_number": "217-333-2291",
        "calendar": {
            "nextSevenDays": [
                {
                    "date": "08/19/2026",
                    "day": "Today",
                    "hours": [
                        {
                            "label": "08:30 AM - 05:00 PM",
                            "startTime": "2026-08-19T08:30:00",
                            "endTime": "2026-08-19T17:00:00",
                        }
                    ],
                },
                {"date": "08/22/2026", "day": "Saturday", "hours": []},
            ]
        },
    }
]


def test_extracts_unit_name_and_hours() -> None:
    result = parse_library_hours(json.dumps(_SAMPLE_RESPONSE).encode("utf-8"))
    assert "Main Library" in result.text
    assert "08:30 AM - 05:00 PM" in result.text


def test_closed_day_reads_as_closed_not_a_blank() -> None:
    result = parse_library_hours(json.dumps(_SAMPLE_RESPONSE).encode("utf-8"))
    assert "Saturday (08/22/2026): closed all day" in result.text


def test_todays_line_is_open_right_now_phrased_and_self_contained() -> None:
    # Every non-"Today" line only says "hours" and the unit name once, so on a real
    # "library hours" question every day scores equally on query-term overlap and the picker
    # (ExtractiveAnswerGenerator, one sentence per chunk by raw overlap then length) needs
    # something to reliably prefer -- today's line is deliberately longer and includes "open
    # right now" so it wins that tie-break on realistic phrasings.
    result = parse_library_hours(json.dumps(_SAMPLE_RESPONSE).encode("utf-8"))
    today_line = next(line for line in result.text.split("\n") if "open right now" in line)
    assert "08:30 AM - 05:00 PM" in today_line
    other_lines = [
        line for line in result.text.split("\n") if line != today_line and "Main Library" in line
    ]
    assert all(len(today_line) >= len(line) for line in other_lines)


def test_includes_address_and_phone() -> None:
    result = parse_library_hours(json.dumps(_SAMPLE_RESPONSE).encode("utf-8"))
    assert "1408 West Gregory Drive" in result.text
    assert "217-333-2291" in result.text


def test_title_uses_unit_name() -> None:
    result = parse_library_hours(json.dumps(_SAMPLE_RESPONSE).encode("utf-8"))
    assert result.title == "Main Library Hours"


def test_falls_back_to_provided_title_when_unit_name_missing() -> None:
    payload = [{k: v for k, v in _SAMPLE_RESPONSE[0].items() if k != "unit_name"}]
    result = parse_library_hours(json.dumps(payload).encode("utf-8"), fallback_title="Library Hours")
    assert result.title == "Library Hours Hours"


def test_handles_missing_calendar_gracefully() -> None:
    payload = [{"unit_name": "Main Library"}]
    result = parse_library_hours(json.dumps(payload).encode("utf-8"))
    assert "Main Library hours for the next seven days:" in result.text
