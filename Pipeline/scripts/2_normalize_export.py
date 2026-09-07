#!/usr/bin/env python3
"""
2_normalize_export.py
-----------------------
Takes one raw WhatsApp export and produces a normalized version where
every sender label has been replaced with their canonical identity name.

Nothing is deleted. Media placeholders (<Media omitted> etc.), deleted-
message notices, missed-call notices, system/group events, and anything
in an unrecognized format are all kept in the output — recognized cases
just get counted separately in the summary so you know they're there.
Only genuinely blank lines are skipped.

Any sender label not yet known in identities.json will be asked about
right there in the terminal, and identities.json is updated immediately
(so you never lose progress if you stop partway through).

Usage:
    cd Pipeline/scripts
    python 2_normalize_export.py ../../Raw_Exports/2026-09_raw.txt

Output:
    ../normalized_exports/2026-09_normalized.txt
"""
import sys
from pathlib import Path
from common import parse_export, load_identities, save_identities, is_media_or_deleted, warn_if_suspicious, resolve_mentions

PIPELINE_DIR = Path(__file__).parent.parent
IDENTITIES_PATH = PIPELINE_DIR / "identities.json"
NORMALIZED_DIR = PIPELINE_DIR / "normalized_exports"


def resolve_sender(sender, data, alias_map, skipped_cache):
    key = sender.strip().lower()
    if key in alias_map:
        return alias_map[key]
    if key in skipped_cache:
        # Already asked about this exact label earlier in this same run
        # and it was skipped — don't ask again for every message from
        # the same person in the same file.
        return skipped_cache[key]

    print(f"\nUnrecognized sender label: '{sender}'")
    names_list = [p['name'] for p in data['identities']]
    if names_list:
        print("Existing identities: " + ", ".join(names_list))
    choice = input("Existing name / NEW name / Enter to leave label as-is: ").strip()

    if not choice:
        # Leave unresolved — it'll be tagged in the output so it's easy to
        # find with a search later, and will be asked about again next
        # time (a future export), but not again within this run.
        tag = f"{sender.strip()} [UNRESOLVED]"
        skipped_cache[key] = tag
        return tag

    existing = next((p for p in data['identities'] if p['name'].lower() == choice.lower()), None)
    if existing:
        existing['aliases'].append(sender.strip())
        alias_map[key] = existing['name']
        return existing['name']
    else:
        data['identities'].append({"name": choice, "aliases": [sender.strip()]})
        alias_map[key] = choice
        return choice


def main():
    if len(sys.argv) != 2:
        print("Usage: python 2_normalize_export.py <raw_export.txt>")
        sys.exit(1)

    raw_path = Path(sys.argv[1])
    if not raw_path.exists():
        print(f"File not found: {raw_path}")
        sys.exit(1)

    data, alias_map = load_identities(IDENTITIES_PATH)

    with open(raw_path, 'r', encoding='utf-8', errors='replace') as f:
        raw_line_count = sum(1 for l in f if l.strip())
    messages = parse_export(raw_path)
    warn_if_suspicious(raw_path, messages, raw_line_count)

    out_lines = []
    media_count = 0
    unparsed_count = 0
    skipped_cache = {}

    for m in messages:
        if m.get('unparsed'):
            # Matched no known pattern at all — kept verbatim, flagged,
            # never dropped.
            out_lines.append(f"[UNPARSED - review this line] {m['msg']}")
            unparsed_count += 1
            continue

        if m['sender'] is None:
            # System/event line (e.g. "X added Y", "X changed the subject").
            # Kept for context, tagged so it's easy to filter out later if
            # you'd rather not see them — just search/remove "[SYSTEM]" lines.
            event_text = resolve_mentions(m['msg'], alias_map)
            out_lines.append(f"{m['date']}, {m['time']} - [SYSTEM] {event_text}")
        else:
            if is_media_or_deleted(m['msg']):
                media_count += 1  # counted for the summary, not dropped
            canon = resolve_sender(m['sender'], data, alias_map, skipped_cache)
            msg_text = resolve_mentions(m['msg'], alias_map)
            out_lines.append(f"{m['date']}, {m['time']} - {canon}: {msg_text}")

    save_identities(data, IDENTITIES_PATH)

    NORMALIZED_DIR.mkdir(exist_ok=True)
    out_name = raw_path.stem.replace('_raw', '') + '_normalized.txt'
    out_path = NORMALIZED_DIR / out_name
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(out_lines) + '\n')

    print(f"\nDone. {len(out_lines)} lines written (nothing dropped).")
    print(f"  Of those: {media_count} media/deleted/call placeholders, "
          f"{unparsed_count} unparsed line(s) flagged for review.")
    print(f"Saved to: {out_path}")

    if unparsed_count:
        print(f"\nNote: {unparsed_count} line(s) didn't match any known "
              f"format and were kept verbatim, tagged '[UNPARSED - review "
              f"this line]'. Search for that tag in the output to find and "
              f"check them.")

    if '[UNRESOLVED]' in '\n'.join(out_lines):
        print("\nNote: some senders were left unresolved and tagged '[UNRESOLVED]'. "
              "Run this script again later (or edit identities.json by hand) to fix them.")


if __name__ == "__main__":
    main()

