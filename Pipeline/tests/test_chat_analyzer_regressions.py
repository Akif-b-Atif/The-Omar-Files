import sys
from pathlib import Path

import pandas as pd

ANALYZER_DIR = Path(__file__).parent.parent / "Tools" / "chat_analyzer"
sys.path.insert(0, str(ANALYZER_DIR))

from parsing import build_dataframe  # noqa: E402
from search_export import build_search_data  # noqa: E402
from stats_engine import (  # noqa: E402
    _build_phrase_index,
    _clean_for_wordphrase,
    _compile_mention_patterns,
    _compute_mentions,
    compute_overall,
    prepare_lexical_text,
)
import chat_config as cfg  # noqa: E402


def _records(messages):
    return [
        {
            "date_s": "21-Oct-2026",
            "time_s": f"00:{minute:02d}",
            "sender": sender,
            "text": text,
            "is_system": False,
        }
        for minute, sender, text in messages
    ]


def test_media_placeholders_and_waiting_notice_are_not_lexical_text():
    records = _records([
        (0, "Alice", "<sticker omitted>"),
        (1, "Alice", "<image omitted>"),
        (2, "Alice", "<GIF omitted>"),
        (3, "Alice", "<video omitted> check this out right now"),
        (4, "Alice", "<forwarded image omitted>"),
        (5, "Alice", "<album omitted>"),
        (6, "Alice", "<voice message omitted>"),
        (7, "Alice", "<forwarded video omitted>"),
        (8, "Alice", "Waiting for this message. This may take a while."),
        (9, "Alice", "[UNPARSED - review this line] raw status text"),
    ])
    df = build_dataframe(records)

    assert df["is_media"].tolist() == [
        True, True, True, True, True, True, True, True, False, False
    ]
    assert df["analysis_text"].tolist() == [
        "", "", "", "check this out right now", "", "", "", "", "", "",
    ]
    assert df["is_real_text"].tolist() == [
        False, False, False, True, False, False, False, False, False, False
    ]
    assert df.loc[3, "word_count"] == 5
    assert df.loc[3, "text"] == "<video omitted> check this out right now"


def test_known_multiword_unicode_mentions_are_attributed_and_removed():
    participants = ["Alice Smith", "Bob-Jones", "Other"]
    aliases = {"señor bob": "Bob-Jones"}
    pattern, _ = _compile_mention_patterns(participants, aliases)
    text = "@Alice Smith @Señor Bob @all"

    assert _clean_for_wordphrase(text, pattern).strip() == ""
    real = pd.DataFrame([{
        "sender": "Other",
        "analysis_text": text,
    }])
    given, received, pairs = _compute_mentions(real, participants, aliases)
    assert given["Other"] == 2
    assert received["Alice Smith"] == 1
    assert received["Bob-Jones"] == 1
    assert sum(received.values()) == 2
    assert len(pairs) == 2


def test_known_alias_for_filtered_participant_is_removed_but_not_attributed():
    aliases = {"señor bob": "Bob-Jones"}
    df = build_dataframe(_records([
        (0, "Other", "@Señor Bob hello"),
    ]))
    prepared = prepare_lexical_text(df, ["Other"], aliases)
    _, received, pairs = _compute_mentions(df, ["Other"], aliases)

    assert prepared.loc[0, "lexical_text"].strip() == "hello"
    assert not received
    assert not pairs


def test_ambiguous_first_name_is_not_attributed_and_lexical_word_count_excludes_mentions():
    participants = ["Sam One", "Sam Two", "Bob-Jones"]
    aliases = {"nickname": "Bob-Jones"}
    df = build_dataframe(_records([
        (0, "Sam One", "@Sam hello"),
        (1, "Sam One", "@nickname welcome"),
    ]))
    prepared = prepare_lexical_text(df, participants, aliases)

    assert prepared["word_count"].tolist() == [1, 1]
    _, received, _ = _compute_mentions(df, participants, aliases)
    assert received == {"Bob-Jones": 1}


def test_median_reply_gap_ignores_same_sender_double_texts():
    df = build_dataframe(_records([
        (0, "A", "first"),
        (1, "A", "double text"),
        (11, "B", "reply"),
        (30, "B", "another double text"),
    ]))

    assert compute_overall(df)["median_reply_gap_minutes"] == 10


def test_captioned_media_remains_searchable():
    df = build_dataframe(_records([
        (0, "A", "<video omitted> check this out right now"),
    ]))
    data = build_search_data(
        df, ["A"], {}, {}, {"by_hour": {}, "by_weekday": {}}
    )

    assert data["flags"] == [1]
    assert data["texts"] == ["check this out right now"]
    assert compute_overall(df)["total_text_messages"] == 0
    assert compute_overall(df)["total_media"] == 1


def test_unknown_album_and_forwarded_markers_do_not_become_phrases():
    df = build_dataframe(_records([
        (0, "A", "<unknown message>"),
        (1, "A", "<unknown message>"),
        (2, "A", "<album message>"),
        (3, "A", "<album message>"),
        (4, "A", "[Forwarded]"),
        (5, "A", "[Forwarded]"),
        (6, "A", "[Forwarded] <image omitted>"),
        (7, "A", "[Forwarded] <video omitted>"),
        (8, "A", "[Forwarded] <video omitted> check this out right now"),
    ]))

    assert df["is_media"].tolist() == [
        True, True, True, True, False, False, True, True, True
    ]
    assert df["analysis_text"].tolist() == [
        "", "", "", "", "", "", "", "", "check this out right now"
    ]
    assert df["is_real_text"].tolist() == [
        False, False, False, False, False, False, False, False, True
    ]
    phrases = _build_phrase_index(df, cfg)["counter"]
    assert phrases == {"check this out right now": 1}


def test_future_archive_dates_are_preserved():
    df = build_dataframe([{
        "date_s": "10-Dec-2026",
        "time_s": "12:00",
        "sender": "A",
        "text": "valid future archive date",
        "is_system": False,
    }])

    assert pd.Timestamp(df["timestamp"].max()).date().isoformat() == "2026-12-10"


# ---------------------------------------------------------------------------
# Identity / mention regressions
# ---------------------------------------------------------------------------

def test_isolate_wrapped_tag_never_becomes_a_phrase():
    """A message that is only "@<FSI>Akif Bin Atif<PDI>" used to leave the
    bare name behind (the isolate hid the name from both the tag regex and
    the mention matcher) and top the repeated-phrases list."""
    tag = "@\u2068Akif Bin Atif\u2069"
    df = build_dataframe(_records([(i, "Alice", tag) for i in range(5)]))
    pattern, _ = _compile_mention_patterns(["Alice", "Akif"], {"akif bin atif": "Akif"})
    df = prepare_lexical_text(df, ["Alice", "Akif"], {"akif bin atif": "Akif"})
    idx = _build_phrase_index(df, cfg, mention_pattern=pattern)
    assert idx["counter"] == {}
    assert "akif" not in " ".join(df["lexical_text"]).lower()


def test_isolate_wrapped_tag_counts_as_a_mention():
    df = build_dataframe(_records([(0, "Alice", "@\u2068Akif Bin Atif\u2069 hey")]))
    _, received, pairs = _compute_mentions(df, ["Alice", "Akif"], {"akif bin atif": "Akif"})
    assert received["Akif"] == 1 and pairs[0]["from"] == "Alice"


def test_exact_name_beats_first_name_of_longer_name():
    _, lookup = _compile_mention_patterns(["Abdullah", "Abdullah Hanif", "Ahmed N.", "Ahmed T."])
    assert lookup["abdullah"] == "Abdullah"
    assert "ahmed" not in lookup  # genuinely ambiguous first name


def test_possessive_tag_matches_but_embedded_at_does_not():
    pattern, _ = _compile_mention_patterns(["Omar"])
    assert pattern.search("@Omar's phone")
    assert not pattern.search("mail me@Omar")
    assert not pattern.search("@Omar-ish")


def test_system_line_with_colon_and_long_sender_are_parsed_correctly(tmp_path):
    from parsing import parse_chat_file
    long_label = "A Very Long Display Name That Goes Past Forty Characters [UNRESOLVED]"
    path = tmp_path / "a.txt"
    path.write_text(
        "01-Aug-2026, 00:32 - [SYSTEM] Omar renamed: it\n"
        f"01-Aug-2026, 00:33 - {long_label}: hello\n", encoding="utf-8")
    recs = parse_chat_file(path)
    assert recs[0]["is_system"] and recs[0]["sender"] is None
    assert recs[1]["sender"] == long_label and not recs[1]["is_system"]


def test_same_minute_messages_keep_archive_order():
    df = build_dataframe([
        {"date_s": "01-Aug-2026", "time_s": "10:00", "sender": "Alice",
         "text": f"m{i}", "is_system": False} for i in range(40)
    ])
    assert df["text"].tolist() == [f"m{i}" for i in range(40)]


def test_non_latin_words_are_counted():
    from parsing import tokenize
    assert tokenize("don’t عصّین hello") == ["don't", "عصّین", "hello"]
    df = build_dataframe(_records([(0, "Alice", "مرحبا بك")]))
    assert df.loc[0, "word_count"] == 2


def test_nickname_parts_that_are_ordinary_words_stay_in_word_stats(tmp_path):
    import json
    import chat_config
    ids = tmp_path / "ids.json"
    ids.write_text(json.dumps({"identities": [
        {"name": "Zephyrine", "aliases": ["Big Zeph"]}]}), encoding="utf-8")
    tokens = chat_config._name_tokens_from_identities(ids)
    assert "zephyrine" in tokens and "zeph" in tokens
    assert "big" not in tokens
