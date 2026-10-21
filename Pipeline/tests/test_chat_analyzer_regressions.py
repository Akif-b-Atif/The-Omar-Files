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
        (0, "Akif", "<sticker omitted>"),
        (1, "Akif", "<image omitted>"),
        (2, "Akif", "<GIF omitted>"),
        (3, "Akif", "<video omitted> Viva mein phat-te hue"),
        (4, "Akif", "<forwarded image omitted>"),
        (5, "Akif", "<album omitted>"),
        (6, "Akif", "<voice message omitted>"),
        (7, "Akif", "<forwarded video omitted>"),
        (8, "Akif", "Waiting for this message. This may take a while."),
        (9, "Akif", "[UNPARSED - review this line] raw status text"),
    ])
    df = build_dataframe(records)

    assert df["is_media"].tolist() == [
        True, True, True, True, True, True, True, True, False, False
    ]
    assert df["analysis_text"].tolist() == [
        "", "", "", "Viva mein phat-te hue", "", "", "", "", "", "",
    ]
    assert df["is_real_text"].tolist() == [
        False, False, False, True, False, False, False, False, False, False
    ]
    assert df.loc[3, "word_count"] == 5
    assert df.loc[3, "text"] == "<video omitted> Viva mein phat-te hue"


def test_known_multiword_unicode_mentions_are_attributed_and_removed():
    participants = ["Akif Bin Atif", "Aarij-ul-Eman", "Other"]
    aliases = {"señor aarij": "Aarij-ul-Eman"}
    pattern, _ = _compile_mention_patterns(participants, aliases)
    text = "@Akif Bin Atif @Señor Aarij @all"

    assert _clean_for_wordphrase(text, pattern).strip() == ""
    real = pd.DataFrame([{
        "sender": "Other",
        "analysis_text": text,
    }])
    given, received, pairs = _compute_mentions(real, participants, aliases)
    assert given["Other"] == 2
    assert received["Akif Bin Atif"] == 1
    assert received["Aarij-ul-Eman"] == 1
    assert sum(received.values()) == 2
    assert len(pairs) == 2


def test_known_alias_for_filtered_participant_is_removed_but_not_attributed():
    aliases = {"señor aarij": "Aarij-ul-Eman"}
    df = build_dataframe(_records([
        (0, "Other", "@Señor Aarij hello"),
    ]))
    prepared = prepare_lexical_text(df, ["Other"], aliases)
    _, received, pairs = _compute_mentions(df, ["Other"], aliases)

    assert prepared.loc[0, "lexical_text"].strip() == "hello"
    assert not received
    assert not pairs


def test_ambiguous_first_name_is_not_attributed_and_lexical_word_count_excludes_mentions():
    participants = ["Sam One", "Sam Two", "Aarij-ul-Eman"]
    aliases = {"nickname": "Aarij-ul-Eman"}
    df = build_dataframe(_records([
        (0, "Sam One", "@Sam hello"),
        (1, "Sam One", "@nickname welcome"),
    ]))
    prepared = prepare_lexical_text(df, participants, aliases)

    assert prepared["word_count"].tolist() == [1, 1]
    _, received, _ = _compute_mentions(df, participants, aliases)
    assert received == {"Aarij-ul-Eman": 1}


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
        (0, "A", "<video omitted> Viva mein phat-te hue"),
    ]))
    data = build_search_data(
        df, ["A"], {}, {}, {"by_hour": {}, "by_weekday": {}}
    )

    assert data["flags"] == [1]
    assert data["texts"] == ["Viva mein phat-te hue"]
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
        (8, "A", "[Forwarded] <video omitted> Viva mein phat-te hue"),
    ]))

    assert df["is_media"].tolist() == [
        True, True, True, True, False, False, True, True, True
    ]
    assert df["analysis_text"].tolist() == [
        "", "", "", "", "", "", "", "", "Viva mein phat-te hue"
    ]
    assert df["is_real_text"].tolist() == [
        False, False, False, False, False, False, False, False, True
    ]
    phrases = _build_phrase_index(df, cfg)["counter"]
    assert phrases == {"viva mein phat te hue": 1}


def test_future_archive_dates_are_preserved():
    df = build_dataframe([{
        "date_s": "10-Dec-2026",
        "time_s": "12:00",
        "sender": "A",
        "text": "valid future archive date",
        "is_system": False,
    }])

    assert pd.Timestamp(df["timestamp"].max()).date().isoformat() == "2026-12-10"
