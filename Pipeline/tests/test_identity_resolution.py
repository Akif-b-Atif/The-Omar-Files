"""
test_identity_resolution.py -- regression tests for sender/@-mention
identity resolution: the alias key, mention resolution (number AND
contact-name forms), system events with a colon in them, paragraph
breaks, and normalize_messages() end to end.
"""
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from omar_identities import alias_key, build_alias_map  # noqa: E402
from common import (  # noqa: E402
    assign_alias, load_identities, parse_export, parse_normalized_blocks,
    resolve_mentions,
)
from normalize_export import normalize_messages  # noqa: E402

FSI, PDI = "\u2068", "\u2069"

IDENTITIES = {"identities": [
    {"name": "Ahsan", "aliases": ["95005062480096@lid", "+966 58 371 5010",
                                  "SuperAhsan Ali", "Junior Mossad Agent Ahsan"]},
    {"name": "Akif", "aliases": ["923221305103@s.whatsapp.net", "Akifa❤️❤️ 🌹",
                                 "Akif Bin Atif", "AKIF BIN ATIF"]},
    {"name": "Ahmed N.", "aliases": ["966578926676@s.whatsapp.net", "عصّین"]},
]}


def _alias_map():
    return build_alias_map(IDENTITIES)[0]


def test_alias_key_ignores_case_variation_selector_isolates_and_tilde():
    assert alias_key("AKIF BIN ATIF") == alias_key("Akif Bin Atif")
    assert alias_key("Akifa❤\ufe0f") == alias_key("Akifa❤")
    assert alias_key(f"{FSI}Akif{PDI}") == alias_key("akif")
    assert alias_key("~\u202fSomeone") == alias_key("Someone")


def test_canonical_names_are_implicit_aliases():
    assert _alias_map()[alias_key("Akif")] == "Akif"


def test_conflicting_alias_is_reported_not_silently_overwritten():
    data = {"identities": [{"name": "A", "aliases": ["Sam"]},
                           {"name": "B", "aliases": ["sam"]}]}
    alias_map, conflicts = build_alias_map(data)
    assert conflicts == {"sam": {"A", "B"}}
    assert alias_map["sam"] == "A"  # first claimant wins; analyzer drops it


def test_contact_name_mentions_resolve_and_lose_their_isolates():
    am = _alias_map()
    for label in ("SuperAhsan Ali", "Junior Mossad Agent Ahsan"):
        assert resolve_mentions(f"@{FSI}{label}{PDI} where u at", am) == "@Ahsan where u at"


def test_formatted_phone_number_mention_resolves():
    assert resolve_mentions(f"@{FSI}+966 58 371 5010{PDI} yo", _alias_map()) == "@Ahsan yo"


def test_bare_number_mention_still_resolves():
    assert resolve_mentions("hi @966578926676", _alias_map()) == "hi @Ahmed N."


def test_unresolved_mentions_are_kept_stripped_of_isolates_and_counted():
    unresolved = Counter()
    out = resolve_mentions(f"@{FSI}Some Stranger{PDI} hi, @{FSI}Some Stranger{PDI}",
                           _alias_map(), unresolved)
    assert out == "@Some Stranger hi, @Some Stranger"
    assert unresolved == Counter({"Some Stranger": 2})


def test_email_like_text_is_not_a_mention():
    assert resolve_mentions("mail me@966578926676", _alias_map()) == "mail me@966578926676"


def test_same_message_from_two_phones_normalizes_identically(tmp_path):
    """The duplicated-tag bug: two exports that saved the same person under
    different contact names must produce the same archive line."""
    am = _alias_map()
    lines = []
    for contact in ("SuperAhsan Ali", "Junior Mossad Agent Ahsan"):
        raw = tmp_path / "raw.txt"
        raw.write_text(f"8/1/26, 12:32 AM - Ahmed N.: @{FSI}{contact}{PDI} where u at\n"
                       "8/1/26, 12:33 AM - Ahmed N.: Kya\n", encoding="utf-8")
        data = {"identities": [dict(p) for p in IDENTITIES["identities"]]}
        result = normalize_messages(parse_export(raw, day_first=False), data, dict(am), tmp_path / "ids.json")
        lines.append(result.lines)
    assert lines[0] == lines[1]
    assert lines[0][0] == "01-Aug-2026, 00:32 - Ahmed N.: @Ahsan where u at"


def test_system_event_containing_a_colon_is_not_a_message(tmp_path):
    raw = tmp_path / "raw.txt"
    raw.write_text("8/1/26, 12:15 AM - Omar changed the group description: new text\n"
                   "8/1/26, 12:16 AM - Ahmed N.: hi\n", encoding="utf-8")
    msgs = parse_export(raw)
    assert msgs[0]["sender"] is None
    assert msgs[0]["msg"] == "Omar changed the group description: new text"
    assert msgs[1]["sender"] == "Ahmed N."


def test_blank_line_inside_a_message_survives_normalize_and_reparse(tmp_path):
    raw = tmp_path / "raw.txt"
    raw.write_text("2026-08-01 10:00:00 Alice: para one\n\npara two\n\n"
                   "2026-08-01 10:01:00 Bob: next\n", encoding="utf-8")
    msgs = parse_export(raw)
    assert msgs[0]["msg"] == "para one\n\npara two"
    assert msgs[1]["msg"] == "next"  # blank line between messages is spacing

    archive = tmp_path / "archive.txt"
    archive.write_text("01-Aug-2026, 10:00 - Alice: para one\n\npara two\n\n"
                       "01-Aug-2026, 10:01 - Bob: next\n", encoding="utf-8")
    blocks = parse_normalized_blocks(archive)
    assert [b["text"] for b in blocks] == [
        "01-Aug-2026, 10:00 - Alice: para one\n\npara two",
        "01-Aug-2026, 10:01 - Bob: next",
    ]


def test_assign_alias_is_idempotent_and_case_insensitive():
    data = {"identities": [{"name": "Akif", "aliases": []}]}
    alias_map = {}
    assert assign_alias(data, alias_map, "Akif B", "akif") == "Akif"
    assert assign_alias(data, alias_map, "Akif B", "AKIF") == "Akif"
    assert data["identities"][0]["aliases"] == ["Akif B"]
    assert alias_map[alias_key("akif b")] == "Akif"


def test_load_identities_warns_about_conflicts(tmp_path, capsys):
    path = tmp_path / "ids.json"
    path.write_text('{"identities": [{"name": "A", "aliases": ["x"]},'
                    '{"name": "B", "aliases": ["X"]}]}', encoding="utf-8")
    _, alias_map = load_identities(path)
    assert alias_map["x"] == "A"
    assert "claimed by more than one identity" in capsys.readouterr().err
