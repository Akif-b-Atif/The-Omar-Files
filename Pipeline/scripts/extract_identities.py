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
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import omar_paths  # noqa: E402
from common import parse_export, load_identities, save_identities, warn_if_suspicious  # noqa: E402


def main():
    if len(sys.argv) < 2:
        print("Usage: python extract_identities.py <raw_export.txt> [more files...]")
        sys.exit(1)

    try:
        IDENTITIES_PATH = omar_paths.require_paths().identities
    except omar_paths.DataDirError as e:
        sys.exit(str(e))
    data, alias_map = load_identities(IDENTITIES_PATH)

    unknown = {}
    for filepath in sys.argv[1:]:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            raw_line_count = sum(1 for l in f if l.strip())
        messages = parse_export(filepath)
        warn_if_suspicious(filepath, messages, raw_line_count)
        for msg in messages:
            sender = msg['sender']
            if sender is None:
                continue
            key = sender.strip().lower()
            if key not in alias_map:
                unknown[sender.strip()] = unknown.get(sender.strip(), 0) + 1

    if not unknown:
        print("No unknown senders found — identities.json already covers everyone in these files.")
        return

    print(f"Found {len(unknown)} unrecognized sender label(s). Going through them, "
          f"most frequent first.\n")

    for sender, count in sorted(unknown.items(), key=lambda x: -x[1]):
        names_list = [p['name'] for p in data['identities']]
        print(f"\n--- '{sender}'  (appears {count} times) ---")
        if names_list:
            print("Existing identities: " + ", ".join(names_list))
        choice = input(
            "Type an EXISTING name to add this as an alias, "
            "a NEW name to create a new identity, "
            "or just press Enter to skip for now: "
        ).strip()

        if not choice:
            print("Skipped (will show up again next time you run this).")
            continue

        existing = next((p for p in data['identities'] if p['name'].lower() == choice.lower()), None)
        if existing:
            existing['aliases'].append(sender)
            alias_map[sender.lower()] = existing['name']
            print(f"Added '{sender}' as an alias of {existing['name']}.")
        else:
            data['identities'].append({"name": choice, "aliases": [sender]})
            alias_map[sender.lower()] = choice
            print(f"Created new identity '{choice}' with alias '{sender}'.")

        save_identities(data, IDENTITIES_PATH)  # save after every answer, no lost progress

    print(f"\nDone. identities.json now has {len(data['identities'])} identities.")


if __name__ == "__main__":
    main()
