"""
test_merge.py — unit tests for the chronological merge + dedup logic in
Pipeline/scripts/merge_export.py.

This is the one piece of the pipeline where a bug has real consequences
(a duplicated or dropped message in someone's only copy of their chat
history), so it gets tested directly against parse_normalized_blocks()
output rather than only via the end-to-end smoke test.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from common import parse_normalized_blocks, extract_slot_key  # noqa: E402

import merge_export  # noqa: E402

archive_text_counts = merge_export.archive_text_counts
decompose = merge_export.decompose
merge_dated_sequences = merge_export.merge_dated_sequences
is_superseded = merge_export.is_superseded


def _blocks(text):
    """Write text to a temp-ish in-memory file substitute by reusing
    parse_normalized_blocks' line-based logic directly on a list."""
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write(text)
        path = Path(f.name)
    try:
        return parse_normalized_blocks(path)
    finally:
        path.unlink()


ARCHIVE_TEXT = (
    "13-Dec-2024, 03:17 - Alice Smith: hello\n"
    "13-Dec-2024, 03:18 - Bob Jones: hi back\n"
)


def test_merge_adds_genuinely_new_message():
    archive_blocks = _blocks(ARCHIVE_TEXT)
    new_blocks = _blocks("13-Dec-2024, 03:19 - Alice Smith: how are you\n")

    a_leading, a_dated = decompose(archive_blocks)
    b_leading, b_dated = decompose(new_blocks)
    available = archive_text_counts(archive_blocks)
    archive_slots = {extract_slot_key(b['text']) for b in archive_blocks} - {None}

    merged, added, dup, ph = merge_dated_sequences(a_dated, b_dated, available, archive_slots)
    assert added == 1
    assert dup == 0
    assert ph == 0
    assert len(merged) == 3


def test_merge_skips_exact_duplicate():
    archive_blocks = _blocks(ARCHIVE_TEXT)
    new_blocks = _blocks(ARCHIVE_TEXT)  # identical re-export

    a_leading, a_dated = decompose(archive_blocks)
    b_leading, b_dated = decompose(new_blocks)
    available = archive_text_counts(archive_blocks)
    archive_slots = {extract_slot_key(b['text']) for b in archive_blocks} - {None}

    merged, added, dup, ph = merge_dated_sequences(a_dated, b_dated, available, archive_slots)
    assert added == 0
    assert dup == 2
    assert len(merged) == 2  # nothing duplicated in the output


def test_merge_is_idempotent_on_repeated_full_reruns():
    """Running the same merge twice in a row should never grow the
    archive the second time — this is the property the docs promise
    ("safe to re-run")."""
    archive_blocks = _blocks(ARCHIVE_TEXT)
    new_blocks = _blocks("13-Dec-2024, 03:19 - Alice Smith: how are you\n")

    a_leading, a_dated = decompose(archive_blocks)
    b_leading, b_dated = decompose(new_blocks)
    available = archive_text_counts(archive_blocks)
    archive_slots = {extract_slot_key(b['text']) for b in archive_blocks} - {None}
    merged, added, dup, ph = merge_dated_sequences(a_dated, b_dated, available, archive_slots)
    assert added == 1

    # Re-run against the now-merged archive with the exact same "new" file.
    merged_text = "\n".join(b['text'] for b, _ in merged) + "\n"
    archive_blocks_2 = _blocks(merged_text)
    a_leading2, a_dated2 = decompose(archive_blocks_2)
    available_2 = archive_text_counts(archive_blocks_2)
    archive_slots_2 = {extract_slot_key(b['text']) for b in archive_blocks_2} - {None}
    merged2, added2, dup2, ph2 = merge_dated_sequences(
        a_dated2, b_dated, available_2, archive_slots_2)
    assert added2 == 0
    assert dup2 == 1


def test_placeholder_superseded_by_existing_real_content():
    archive_blocks = _blocks(ARCHIVE_TEXT)
    # Same (date, time, sender) slot as the first archive line, but with
    # placeholder text instead of the real message.
    new_blocks = _blocks("13-Dec-2024, 03:17 - Alice Smith: waiting for this message\n")

    a_leading, a_dated = decompose(archive_blocks)
    b_leading, b_dated = decompose(new_blocks)
    available = archive_text_counts(archive_blocks)
    archive_slots = {extract_slot_key(b['text']) for b in archive_blocks} - {None}

    merged, added, dup, ph = merge_dated_sequences(a_dated, b_dated, available, archive_slots)
    assert added == 0
    assert ph == 1
    # Archive's real text is untouched.
    assert merged[0][0]['text'] == "13-Dec-2024, 03:17 - Alice Smith: hello"


def test_placeholder_not_superseded_when_slot_is_genuinely_new():
    archive_blocks = _blocks(ARCHIVE_TEXT)
    new_blocks = _blocks("13-Dec-2024, 03:20 - Alice Smith: waiting for this message\n")

    a_leading, a_dated = decompose(archive_blocks)
    b_leading, b_dated = decompose(new_blocks)
    available = archive_text_counts(archive_blocks)
    archive_slots = {extract_slot_key(b['text']) for b in archive_blocks} - {None}

    merged, added, dup, ph = merge_dated_sequences(a_dated, b_dated, available, archive_slots)
    # Genuinely new content (even if it's a placeholder) is kept, not dropped.
    assert added == 1
    assert ph == 0


def test_chronological_insertion_mid_archive():
    archive_text = (
        "01-Jan-2025, 00:00 - Alice: first\n"
        "03-Jan-2025, 00:00 - Alice: third\n"
    )
    new_text = "02-Jan-2025, 00:00 - Alice: second\n"
    archive_blocks = _blocks(archive_text)
    new_blocks = _blocks(new_text)

    a_leading, a_dated = decompose(archive_blocks)
    b_leading, b_dated = decompose(new_blocks)
    available = archive_text_counts(archive_blocks)
    archive_slots = {extract_slot_key(b['text']) for b in archive_blocks} - {None}

    merged, added, dup, ph = merge_dated_sequences(a_dated, b_dated, available, archive_slots)
    ordered_texts = [b['text'] for b, _ in merged]
    assert ordered_texts == [
        "01-Jan-2025, 00:00 - Alice: first",
        "02-Jan-2025, 00:00 - Alice: second",
        "03-Jan-2025, 00:00 - Alice: third",
    ]


def test_decompose_splits_leading_undated_from_dated():
    text = (
        "some undated junk line\n"
        "13-Dec-2024, 03:17 - Alice Smith: hello\n"
    )
    blocks = _blocks(text)
    leading, dated = decompose(blocks)
    assert len(leading) == 1
    assert leading[0]['text'] == "some undated junk line"
    assert len(dated) == 1


# ---------------------------------------------------------------------------
# Regression tests: genuinely repeated messages must survive a merge.
# ---------------------------------------------------------------------------

def _merge(archive_text, new_text):
    archive_blocks = _blocks(archive_text)
    new_blocks = _blocks(new_text)
    _, a_dated = decompose(archive_blocks)
    _, b_dated = decompose(new_blocks)
    available = archive_text_counts(archive_blocks)
    slots = {extract_slot_key(b['text']) for b in archive_blocks} - {None}
    merged, added, dup, ph = merge_dated_sequences(a_dated, b_dated, available, slots)
    return [b['text'] for b, _ in merged], added, dup, ph


def test_identical_messages_in_same_minute_are_both_kept():
    """Two real, identical messages in one minute (same sender, same text)
    must not collapse into one when the second export is merged in."""
    archive = "13-Dec-2024, 03:17 - Alice Smith: hello\n"
    new = (
        "13-Dec-2024, 03:20 - Alice Smith: lol\n"
        "13-Dec-2024, 03:20 - Alice Smith: lol\n"
    )
    texts, added, dup, _ = _merge(archive, new)
    assert added == 2
    assert dup == 0
    assert texts.count("13-Dec-2024, 03:20 - Alice Smith: lol") == 2


def test_repeated_messages_are_idempotent_on_rerun():
    archive = (
        "13-Dec-2024, 03:20 - Alice Smith: lol\n"
        "13-Dec-2024, 03:20 - Alice Smith: lol\n"
    )
    texts, added, dup, _ = _merge(archive, archive)
    assert added == 0
    assert dup == 2
    assert len(texts) == 2


def test_overlap_only_adds_the_extra_copy():
    """Archive has one copy, the new export has two: exactly one is new."""
    archive = "13-Dec-2024, 03:20 - Alice Smith: ok\n"
    new = (
        "13-Dec-2024, 03:20 - Alice Smith: ok\n"
        "13-Dec-2024, 03:20 - Alice Smith: ok\n"
    )
    texts, added, dup, _ = _merge(archive, new)
    assert added == 1
    assert dup == 1
    assert len(texts) == 2


def test_write_atomic_replaces_file_and_leaves_no_temp(tmp_path):
    target = tmp_path / "Full_Archive.txt"
    target.write_text("old\n", encoding="utf-8")
    merge_export.write_atomic(target, "new\n")
    assert target.read_text(encoding="utf-8") == "new\n"
    assert not (tmp_path / "Full_Archive.txt.tmp").exists()
