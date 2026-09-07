#!/usr/bin/env python3
"""
run_new_month.py
------------------
Kept for muscle memory. This is now a thin wrapper around control.py's
`update` command — see control.py for the full control panel (merge-only,
pdf-only, chat-only, arc-only, reports-only, and this one).

Usage (unchanged, from inside this Pipeline folder):
    python3 run_new_month.py 2026-09_raw.txt

Equivalent to:
    python3 control.py update 2026-09_raw.txt
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from control import do_update  # noqa: E402


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 run_new_month.py <raw_export.txt>")
        print("Example: python3 run_new_month.py 2026-09_raw.txt")
        print("\n(For merge-only / pdf-only / chat-only / arc-only / reports-only, "
              "use control.py instead — see Pipeline/control.py or TECHNICAL.md.)")
        sys.exit(1)

    do_update([sys.argv[1]])


if __name__ == "__main__":
    main()
