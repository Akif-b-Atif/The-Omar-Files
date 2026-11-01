#!/usr/bin/env python3
"""
normalize_export.py
-----------------------
Takes one raw WhatsApp export and produces a normalized version where
every sender label has been replaced with their canonical identity name.

Nothing is deleted. Media placeholders (<Media omitted> etc.), deleted-
message notices, missed-call notices, system/group events, and anything
in an unrecognized format are all kept in the output — recognized cases
just get counted separately in the summary so you know they're there.
Only blank lines between messages are skipped (a blank line inside a
multi-paragraph message is part of that message and is kept).

Any sender label not yet known in identities.json will be asked about
right there in the terminal, and identities.json is updated immediately
(so you never lose progress if you stop partway through).

Usage:
    cd Pipeline/scripts
    python normalize_export.py <data dir>/Raw_Exports/2026-09_raw.txt

Output:
    <data dir>/normalized_exports/2026-09_normalized.txt
"""
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import omar_paths  # noqa: E402
from omar_identities import alias_key, strip_isolates  # noqa: E402
from common import (  # noqa: E402
    parse_export, load_identities, save_identities, is_media_or_deleted,
    warn_if_suspicious, resolve_mentions, assign_alias,
)

UNRESOLVED_TAG = "[UNRESOLVED]"


@dataclass
class NormalizeResult:
    lines: list = field(default_factory=list)
    media_count: int = 0
    unparsed_count: int = 0
    unresolved_mentions: Counter = field(default_factory=Counter)


def resolve_sender(sender, data, alias_map, skipped_cache, identities_path):
    """Canonical name for a raw sender label, asking in the terminal about
    labels identities.json doesn't know yet. Every answer is written to
    identities.json immediately, so stopping partway never loses progress."""
    label = strip_isolates(sender).strip()
    key = alias_key(label)
    if key in alias_map:
        return alias_map[key]
    if key in skipped_cache:
        # Already asked about this exact label earlier in this same run
        # and it was skipped — don't ask again for every message from
        # the same person in the same file.
        return skipped_cache[key]

    print(f"\nUnrecognized sender label: '{label}'")
    names_list = [p['name'] for p in data['identities']]
    if names_list:
        print("Existing identities: " + ", ".join(names_list))
    try:
        choice = input("Existing name / NEW name / Enter to leave label as-is: ").strip()
    except EOFError:  # no terminal attached: treat like "leave as-is"
        choice = ""

    if not choice:
        # Leave unresolved — it'll be tagged in the output so it's easy to
        # find with a search later, and will be asked about again next
        # time (a future export), but not again within this run.
        tag = f"{label} {UNRESOLVED_TAG}"
        skipped_cache[key] = tag
        return tag

    canonical = assign_alias(data, alias_map, label, choice)
    save_identities(data, identities_path)
    return canonical


def normalize_messages(messages, data, alias_map, identities_path):
    """Turns parsed raw messages into normalized archive lines: canonical
    sender names, @-mentions resolved to canonical names, nothing dropped."""
    result = NormalizeResult()
    skipped_cache = {}

    for m in messages:
        if m.get('unparsed'):
            # Matched no known pattern at all — kept verbatim, flagged,
            # never dropped.
            result.lines.append(f"[UNPARSED - review this line] {m['msg']}")
            result.unparsed_count += 1
            continue

        text = resolve_mentions(m['msg'], alias_map, result.unresolved_mentions)
        if m['sender'] is None:
            # System/event line (e.g. "X added Y", "X changed the subject").
            # Kept for context, tagged so it's easy to filter out later if
            # you'd rather not see them — just search/remove "[SYSTEM]" lines.
            result.lines.append(f"{m['date']}, {m['time']} - [SYSTEM] {text}")
            continue

        if is_media_or_deleted(m['msg']):
            result.media_count += 1  # counted for the summary, not dropped
        canon = resolve_sender(m['sender'], data, alias_map, skipped_cache, identities_path)
        result.lines.append(f"{m['date']}, {m['time']} - {canon}: {text}")

    return result


def main():
    if len(sys.argv) != 2:
        print("Usage: python normalize_export.py <raw_export.txt>")
        sys.exit(1)

    raw_path = Path(sys.argv[1])
    if not raw_path.exists():
        print(f"File not found: {raw_path}")
        sys.exit(1)

    try:
        paths = omar_paths.require_paths()
    except omar_paths.DataDirError as e:
        sys.exit(str(e))
    identities_path = paths.identities
    normalized_dir = paths.normalized

    data, alias_map = load_identities(identities_path)

    with open(raw_path, 'r', encoding='utf-8', errors='replace') as f:
        raw_line_count = sum(1 for line in f if line.strip())
    messages = parse_export(raw_path)
    warn_if_suspicious(raw_path, messages, raw_line_count)

    result = normalize_messages(messages, data, alias_map, identities_path)
    save_identities(data, identities_path)

    normalized_dir.mkdir(parents=True, exist_ok=True)
    out_name = raw_path.stem.replace('_raw', '') + '_normalized.txt'
    out_path = normalized_dir / out_name
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(result.lines) + '\n')

    print(f"\nDone. {len(result.lines)} lines written (nothing dropped).")
    print(f"  Of those: {result.media_count} media/deleted/call placeholders, "
          f"{result.unparsed_count} unparsed line(s) flagged for review.")
    print(f"Saved to: {out_path}")

    if result.unparsed_count:
        print(f"\nNote: {result.unparsed_count} line(s) didn't match any known "
              f"format and were kept verbatim, tagged '[UNPARSED - review "
              f"this line]'. Search for that tag in the output to find and "
              f"check them.")

    if any(UNRESOLVED_TAG in line for line in result.lines):
        print(f"\nNote: some senders were left unresolved and tagged '{UNRESOLVED_TAG}'. "
              "Run this script again later (or edit identities.json by hand) to fix them.")

    if result.unresolved_mentions:
        print("\nNote: these @-mentions matched no identity, so they were kept as "
              "typed. If the same person is tagged under a different contact name "
              "in another export, the two copies of that message will NOT merge as "
              "duplicates. Add each label below as an alias in identities.json "
              "and re-run:")
        for label, count in result.unresolved_mentions.most_common(25):
            print(f"    @{label}  ({count}x)")


if __name__ == "__main__":
    main()
