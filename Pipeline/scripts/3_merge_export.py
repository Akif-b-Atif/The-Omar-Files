#!/usr/bin/env python3
"""
3_merge_export.py
--------------------
Takes one NORMALIZED export (already run through 2_normalize_export.py)
and merges it into Full_Archive.txt.

Every message in the new file is compared directly against what's
already in the archive (exact text match — both files are written in
the same normalized format, so this is reliable) and only messages that
aren't already present get added, each one inserted at the position its
own timestamp puts it. This means a normal month's export (which comes
after everything currently archived), a chat from before the archive's
current start (a predecessor group, say), and anything with messages
scattered in between all work the same way — there's no need to know in
advance which direction a file goes, and no separate "prepend" script.

This script never rewrites or reformats anything already correct in the
archive. It only ever:
  (a) skips a new-file message that's an exact match for one already in
      the archive, or
  (b) inserts a new-file message, verbatim, at the position its
      timestamp puts it.

A message with no parseable timestamp at all (an "[UNPARSED - review
this line]" entry with nothing before it to attach to) can't be placed
chronologically — those are appended at the very end of the archive,
clearly flagged, rather than guessed into a position that might be
wrong.

One exception to "exact match only": WhatsApp sometimes exports the
oldest few messages still visible in a chat as a "Waiting for this
message..." placeholder instead of their real text, if they hadn't
finished syncing yet at export time. That placeholder text obviously
won't exact-match the real content already sitting in the archive from
when that message was still recent (and synced correctly). So a
placeholder new-file message is treated as already covered — and
skipped, not inserted — whenever the archive already has *some*
message at that same (date, time, sender) slot. The archive's own
content always wins in that case; nothing about the archive is ever
overwritten or reordered. A placeholder that doesn't match anything
already archived (i.e. it's genuinely new, unsynced content past the
archive's current end) is still added like any other message — nothing
is ever silently dropped.

Usage:
    cd Pipeline/scripts
    python3 3_merge_export.py ../normalized_exports/2026-09_normalized.txt

Safe to re-run: re-running on a file that's already fully merged adds
nothing, since every message in it already has an exact match in the
archive.
"""
import sys
import json
from pathlib import Path
from datetime import datetime

from common import parse_normalized_blocks, extract_slot_key, is_placeholder_msg

PIPELINE_DIR = Path(__file__).parent.parent  # Pipeline/
ARCHIVE_PATH = PIPELINE_DIR.parent / "Full_Archive.txt"  # repo root — the most accessible file in the project
LOG_PATH = PIPELINE_DIR / "logs" / "merge_log.json"


def decompose(blocks):
    """
    Splits a block list into (leading_undated, dated_sequence):
      - leading_undated: any dateless blocks before the first dated one
      - dated_sequence: a list of (dated_block, [trailing_undated_blocks])
        pairs, in original file order. A dateless block right after a
        dated one is extremely rare in practice (every multi-line
        message is already folded into its parent block's own text by
        the earlier parsing step) but is handled here regardless, kept
        glued to whichever dated block precedes it.
    """
    leading = []
    dated_seq = []
    i, n = 0, len(blocks)
    while i < n and blocks[i]['datetime'] is None:
        leading.append(blocks[i])
        i += 1
    while i < n:
        dated_block = blocks[i]
        i += 1
        trailing = []
        while i < n and blocks[i]['datetime'] is None:
            trailing.append(blocks[i])
            i += 1
        dated_seq.append((dated_block, trailing))
    return leading, dated_seq


def is_superseded(block, existing_texts, archive_slots):
    """
    True if this new-file block shouldn't be added because the archive
    already has it (or already has something better in its place):
      - an exact text match (the normal duplicate case), or
      - it's a "waiting for this message" placeholder AND the archive
        already has *some* message in that same (date, time, sender)
        slot — i.e. this export just re-saw a message it hadn't
        finished syncing yet, and the archive's own copy (saved back
        when that message was still recent enough to sync correctly)
        is the one to keep. See extract_slot_key/is_placeholder_msg in
        common.py.
    """
    if block['text'] in existing_texts:
        return True
    if is_placeholder_msg(block['text']):
        slot = extract_slot_key(block['text'])
        if slot is not None and slot in archive_slots:
            return True
    return False


def merge_dated_sequences(archive_seq, new_seq, existing_texts, archive_slots):
    """
    Stable chronological merge of two (dated_block, trailing) sequences.
    Both are assumed pre-sorted by datetime. Skips any new_seq entry
    that is_superseded() judges already covered by the archive. On a
    tie (equal datetime), all of archive_seq's entries at that
    timestamp come first, then new_seq's, in new_seq's own original
    order — existing content is never reordered relative to itself.
    Returns (merged_sequence, added_count, skipped_duplicate_count,
    skipped_placeholder_count).
    """
    result = []
    added = 0
    skipped_dup = 0
    skipped_placeholder = 0
    i = j = 0

    def _classify_skip(block):
        nonlocal skipped_dup, skipped_placeholder
        if block['text'] in existing_texts:
            skipped_dup += 1
        else:
            skipped_placeholder += 1

    while i < len(archive_seq) and j < len(new_seq):
        b_block, b_trail = new_seq[j]
        if is_superseded(b_block, existing_texts, archive_slots):
            _classify_skip(b_block)
            j += 1
            continue
        a_block, a_trail = archive_seq[i]
        if a_block['datetime'] <= b_block['datetime']:
            result.append((a_block, a_trail))
            i += 1
        else:
            result.append((b_block, b_trail))
            existing_texts.add(b_block['text'])
            added += 1
            j += 1
    while i < len(archive_seq):
        result.append(archive_seq[i])
        i += 1
    while j < len(new_seq):
        b_block, b_trail = new_seq[j]
        j += 1
        if is_superseded(b_block, existing_texts, archive_slots):
            _classify_skip(b_block)
            continue
        result.append((b_block, b_trail))
        existing_texts.add(b_block['text'])
        added += 1
    return result, added, skipped_dup, skipped_placeholder


def render(leading, dated_seq, trailing_appendix):
    lines = [b['text'] for b in leading]
    for dated_block, trailing in dated_seq:
        lines.append(dated_block['text'])
        lines.extend(t['text'] for t in trailing)
    lines.extend(b['text'] for b in trailing_appendix)
    return lines


def write_log(source_file, added, skipped_dup, skipped_placeholder, note):
    LOG_PATH.parent.mkdir(exist_ok=True)
    log = []
    if LOG_PATH.exists():
        with open(LOG_PATH, 'r', encoding='utf-8') as f:
            log = json.load(f)
    entry = {
        "timestamp": datetime.now().isoformat(timespec='seconds'),
        "source_file": source_file,
        "new_messages_added": added,
        "duplicates_skipped": skipped_dup,
        "placeholders_superseded_by_archive": skipped_placeholder,
    }
    if note:
        entry["note"] = note
    log.append(entry)
    with open(LOG_PATH, 'w', encoding='utf-8') as f:
        json.dump(log, f, indent=2, ensure_ascii=False)


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 3_merge_export.py <normalized_export.txt>")
        sys.exit(1)

    new_path = Path(sys.argv[1])
    if not new_path.exists():
        print(f"File not found: {new_path}")
        sys.exit(1)

    archive_blocks = parse_normalized_blocks(ARCHIVE_PATH)
    new_blocks = parse_normalized_blocks(new_path)

    if not new_blocks:
        print("The normalized export is empty — nothing to merge.")
        return

    if not archive_blocks:
        # First-ever merge: the archive doesn't exist yet, so there's
        # nothing to compare against or insert relative to — the new
        # file becomes the whole archive, exactly as it is.
        with open(ARCHIVE_PATH, 'w', encoding='utf-8') as f:
            f.write('\n'.join(b['text'] for b in new_blocks) + '\n')
        write_log(new_path.name, len(new_blocks), 0, 0, "archive was empty (first merge)")
        print(f"Created {ARCHIVE_PATH.relative_to(PIPELINE_DIR.parent)} with {len(new_blocks)} line(s).")
        return

    a_leading, a_dated = decompose(archive_blocks)
    b_leading, b_dated = decompose(new_blocks)
    # Pre-sort each source by timestamp (stable). Normally already true
    # for a single export — WhatsApp exports are always chronological —
    # but this keeps the merge correct even if that ever isn't the case.
    a_dated.sort(key=lambda pair: pair[0]['datetime'])
    b_dated.sort(key=lambda pair: pair[0]['datetime'])

    existing_texts = set(b['text'] for b in archive_blocks)
    # (date, time, sender) slots the archive already has *some* message
    # in — used only to recognize a re-exported "waiting for this
    # message" placeholder as already covered by real archived content,
    # never to judge any other kind of message. See is_superseded().
    archive_slots = set()
    for b in archive_blocks:
        if b['datetime'] is None:
            continue
        slot = extract_slot_key(b['text'])
        if slot is not None:
            archive_slots.add(slot)

    merged_dated, added, skipped_dup, skipped_placeholder = merge_dated_sequences(
        a_dated, b_dated, existing_texts, archive_slots)

    # New leading-undated content (from the new file) has no timestamp
    # to place it by, so rather than guess, it's appended at the very
    # end, clearly flagged for a manual look.
    appendix = []
    for b in b_leading:
        if is_superseded(b, existing_texts, archive_slots):
            if b['text'] in existing_texts:
                skipped_dup += 1
            else:
                skipped_placeholder += 1
            continue
        appendix.append(b)
        existing_texts.add(b['text'])
        added += 1

    lines = render(a_leading, merged_dated, appendix)

    with open(ARCHIVE_PATH, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')

    notes = []
    if appendix:
        notes.append(f"{len(appendix)} line(s) from this export had no parseable "
                      f"timestamp and were appended at the very end of the archive "
                      f"instead of being placed chronologically — worth a manual look.")
    if skipped_placeholder:
        notes.append(f"{skipped_placeholder} 'waiting for this message' placeholder line(s) "
                      f"were skipped because the archive already has real content in that "
                      f"same date/time/sender slot — the archive's existing content was kept.")
    note = " ".join(notes) or None

    write_log(new_path.name, added, skipped_dup, skipped_placeholder, note)

    total_skipped = skipped_dup + skipped_placeholder
    print(f"Merged {new_path.name} into {ARCHIVE_PATH.relative_to(PIPELINE_DIR.parent)}")
    print(f"  {added} new message(s) added, {total_skipped} already-present message(s) skipped "
          f"({skipped_dup} exact duplicate, {skipped_placeholder} placeholder superseded by archive).")
    if note:
        print(f"  Note: {note}")
    print(f"  Archive now has {len(lines)} total lines.")


if __name__ == "__main__":
    main()
