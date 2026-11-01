#!/usr/bin/env python3
"""
extract_identities.py
------------------------
ONE-TIME (or occasional bulk) tool: scans one or more raw export .txt files
for sender labels that aren't yet in identities.json, and asks you — once —
what canonical name each one belongs to.

This is meant for the big initial port.txt, where there may be dozens of
unfamiliar numbers/labels at once and you want to plow through them all in
one sitting. For a normal monthly export, you don't need this script —
normalize_export.py already asks about unknown senders as it goes.

Usage:
    cd Pipeline/scripts
    python extract_identities.py <data dir>/Raw_Exports/00_initial_port.txt
"""
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import omar_paths  # noqa: E402
from omar_identities import alias_key, strip_isolates  # noqa: E402
from common import (  # noqa: E402
    parse_export, load_identities, save_identities, warn_if_suspicious, assign_alias,
)


def collect_unknown_senders(filepaths, alias_map):
    """{label: message count} for every sender label in the given raw
    exports that alias_map doesn't know. Labels that differ only in
    case/emoji-variation/'~ ' prefix are one label (the first spelling
    seen), since they resolve identically."""
    unknown = Counter()
    spelling = {}  # alias_key -> first spelling seen
    for filepath in filepaths:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            raw_line_count = sum(1 for line in f if line.strip())
        messages = parse_export(filepath)
        warn_if_suspicious(filepath, messages, raw_line_count)
        for msg in messages:
            if msg['sender'] is None:
                continue
            label = strip_isolates(msg['sender']).strip()
            key = alias_key(label)
            if key not in alias_map:
                unknown[spelling.setdefault(key, label)] += 1
    return unknown


def main():
    if len(sys.argv) < 2:
        print("Usage: python extract_identities.py <raw_export.txt> [more files...]")
        sys.exit(1)

    try:
        identities_path = omar_paths.require_paths().identities
    except omar_paths.DataDirError as e:
        sys.exit(str(e))
    data, alias_map = load_identities(identities_path)

    unknown = collect_unknown_senders(sys.argv[1:], alias_map)
    if not unknown:
        print("No unknown senders found — identities.json already covers everyone in these files.")
        return

    print(f"Found {len(unknown)} unrecognized sender label(s). Going through them, "
          f"most frequent first.\n")

    for sender, count in unknown.most_common():
        names_list = [p['name'] for p in data['identities']]
        print(f"\n--- '{sender}'  (appears {count} times) ---")
        if names_list:
            print("Existing identities: " + ", ".join(names_list))
        try:
            choice = input(
                "Type an EXISTING name to add this as an alias, "
                "a NEW name to create a new identity, "
                "or just press Enter to skip for now: "
            ).strip()
        except EOFError:
            choice = ""

        if not choice:
            print("Skipped (will show up again next time you run this).")
            continue

        is_new = not any(p['name'].lower() == choice.lower() for p in data['identities'])
        canonical = assign_alias(data, alias_map, sender, choice)
        print(f"Created new identity '{canonical}' with alias '{sender}'." if is_new
              else f"Added '{sender}' as an alias of {canonical}.")

        save_identities(data, identities_path)  # save after every answer, no lost progress

    print(f"\nDone. identities.json now has {len(data['identities'])} identities.")


if __name__ == "__main__":
    main()
