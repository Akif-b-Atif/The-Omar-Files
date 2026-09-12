"""
test_common.py — unit tests for Pipeline/scripts/common.py

Focused on the two riskiest pieces of the pipeline: flexible date
parsing (it has to guess day/month order from ambiguous input) and the
line-format regexes (real exports come in three different shapes). A
regression here would silently corrupt timestamps or drop messages,
so these are worth pinning down.

Run from anywhere with:
    cd Pipeline && python3 -m pytest tests/ -v
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from common import (  # noqa: E402
    parse_flexible_date,
    normalize_date,
    normalize_time,
    clean_line,
    is_media_or_deleted,
    is_placeholder_msg,
    resolve_mentions,
    extract_slot_key,
    parse_export,
    MSG_LINE_PATTERNS,
)


# ---------------------------------------------------------------------------
# parse_flexible_date
# ---------------------------------------------------------------------------

def test_iso_year_first_is_month_day():
    # "the format I gave" convention: year-first -> (month, day).
    assert parse_flexible_date("2024-12-13") == (2024, 12, 13)


def test_iso_year_first_swaps_when_month_invalid():
    # 2024-13-12 can't be (month=13, day=12); the only valid reading
    # is (month=12, day=13).
    assert parse_flexible_date("2024-13-12") == (2024, 12, 13)


def test_month_name_is_unambiguous():
    assert parse_flexible_date("04-Aug-2025") == (2025, 8, 4)
    assert parse_flexible_date("Aug-04-2025") == (2025, 8, 4)


def test_four_digit_year_not_first_uses_day_first_pref():
    # 12/08/2024 with prefer_day_first=True -> 12 Aug 2024.
    assert parse_flexible_date("12/08/2024", prefer_day_first=True) == (2024, 8, 12)


def test_unambiguous_component_over_12_wins_regardless_of_preference():
    # 25 can't be a month, so it's the day even with prefer_day_first=False.
    assert parse_flexible_date("25/03/2024", prefer_day_first=False) == (2024, 3, 25)


def test_two_digit_year_last_common_short_form():
    assert parse_flexible_date("13-12-24", prefer_day_first=True) == (2024, 12, 13)


def test_two_digit_year_first_when_unambiguous():
    # 99 can't be a day or month (>31), so it's unambiguously the year
    # even in the first position. 2-digit years are always resolved
    # into the 2000s (see normalize_date's `year += 2000`), so this
    # lands on 2099, not 1999.
    result = parse_flexible_date("99-01-15", prefer_day_first=True)
    assert result == (2099, 1, 15)


def test_invalid_date_returns_none():
    assert parse_flexible_date("2024-02-30") is None  # Feb 30 doesn't exist
    assert parse_flexible_date("not a date") is None
    assert parse_flexible_date("1-2") is None  # wrong number of parts


def test_normalize_date_falls_back_to_original_on_failure():
    assert normalize_date("garbage") == "garbage"


def test_normalize_date_output_format():
    assert normalize_date("2024-12-13") == "13-Dec-2024"


# ---------------------------------------------------------------------------
# normalize_time
# ---------------------------------------------------------------------------

def test_normalize_time_24h_with_seconds():
    assert normalize_time("14:23:05") == "14:23"


def test_normalize_time_12h_am_pm():
    assert normalize_time("2:23 PM") == "14:23"
    assert normalize_time("2:23AM") == "02:23"


def test_normalize_time_narrow_nbsp_before_ampm():
    # \u202f is the narrow no-break space WhatsApp sometimes inserts.
    assert normalize_time("2:23\u202fPM") == "14:23"


def test_normalize_time_falls_back_on_garbage():
    assert normalize_time("not a time") == "not a time"


# ---------------------------------------------------------------------------
# line cleaning / classification
# ---------------------------------------------------------------------------

def test_clean_line_strips_invisible_direction_markers():
    line = "12/08/2024, 14:23 \u200e- Omar Khan: hi\n"
    assert "\u200e" not in clean_line(line)
    assert clean_line(line).endswith("hi")


def test_is_media_or_deleted():
    assert is_media_or_deleted("<Media omitted>")
    assert is_media_or_deleted("This message was deleted")
    assert not is_media_or_deleted("just a normal message")


def test_is_placeholder_msg():
    assert is_placeholder_msg("waiting for this message")
    assert not is_placeholder_msg("a real message")


def test_resolve_mentions():
    alias_map = {"923001234567@s.whatsapp.net": "Omar"}
    assert resolve_mentions("hey @923001234567 check this", alias_map) == "hey @Omar check this"
    # Unknown number is left untouched.
    assert resolve_mentions("hey @999999999", alias_map) == "hey @999999999"


# ---------------------------------------------------------------------------
# MSG_LINE_PATTERNS — the three real export shapes
# ---------------------------------------------------------------------------

def _first_match(line):
    for pat in MSG_LINE_PATTERNS:
        m = pat['regex'].match(line)
        if m:
            return m
    return None


def test_plain_iso_style():
    m = _first_match("2024-12-13 03:17:33 Ali Zaman: No wait")
    assert m is not None
    assert m.group('sender') == "Ali Zaman"
    assert m.group('msg') == "No wait"


def test_android_style():
    m = _first_match("12/08/2024, 14:23 - Omar Khan: Message text")
    assert m is not None
    assert m.group('sender') == "Omar Khan"
    assert m.group('msg') == "Message text"


def test_iphone_style():
    m = _first_match("[12/08/2024, 14:23:05] Omar Khan: Message text")
    assert m is not None
    assert m.group('sender') == "Omar Khan"
    assert m.group('msg') == "Message text"


# ---------------------------------------------------------------------------
# parse_export — multi-line messages and unparsed lines
# ---------------------------------------------------------------------------

def test_parse_export_reassembles_multiline_message(tmp_path):
    raw = (
        "2024-12-13 03:17:33 Ali Zaman: line one\n"
        "line two\n"
        "2024-12-13 03:18:00 Omar Khan: next message\n"
    )
    f = tmp_path / "export.txt"
    f.write_text(raw, encoding="utf-8")
    messages = parse_export(f)
    assert len(messages) == 2
    assert messages[0]['msg'] == "line one\nline two"
    assert messages[1]['sender'] == "Omar Khan"


def test_parse_export_flags_leading_unparseable_junk(tmp_path):
    raw = "some junk header with no timestamp\n2024-12-13 03:17:33 Ali Zaman: hi\n"
    f = tmp_path / "export.txt"
    f.write_text(raw, encoding="utf-8")
    messages = parse_export(f)
    assert messages[0]['unparsed'] is True
    assert messages[1]['sender'] == "Ali Zaman"


def test_parse_export_never_drops_lines(tmp_path):
    raw = "2024-12-13 03:17:33 Ali Zaman: hi\ncompletely unrecognized standalone line\n"
    # The second line has no leading dated line of its own and nothing
    # already open to attach to as a continuation only if it comes
    # first; here it attaches to the message above as a continuation,
    # which is correct multi-line behavior, not a drop.
    f = tmp_path / "export.txt"
    f.write_text(raw, encoding="utf-8")
    messages = parse_export(f)
    total_text = "\n".join(m['msg'] for m in messages)
    assert "completely unrecognized standalone line" in total_text


# ---------------------------------------------------------------------------
# extract_slot_key
# ---------------------------------------------------------------------------

def test_extract_slot_key_from_archive_line():
    key = extract_slot_key("13-Dec-2024, 03:17 - Ali Zaman: hello there")
    assert key == ("13-Dec-2024", "03:17", "Ali Zaman")


def test_extract_slot_key_none_for_system_line():
    assert extract_slot_key("13-Dec-2024, 03:17 - Ali added Omar") is None
