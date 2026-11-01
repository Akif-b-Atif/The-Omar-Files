#!/usr/bin/env python3
"""
check_no_private_data.py
------------------------
Exits non-zero if git is tracking anything that looks like chat data.
Used by CI, and usable as a git pre-commit hook:

    ln -s ../../Pipeline/tools_dev/check_no_private_data.py .git/hooks/pre-commit

Standard library only. Intentionally conservative: the sample_data/ folder
(fake, bundled on purpose), *.example.json templates and empty .gitkeep
placeholders are allowed.
"""
import re
import subprocess
import sys

FORBIDDEN = [
    r"^Raw_Exports/(?!\.gitkeep$)",
    r"^Reports/(?!\.gitkeep$)",
    r"^data/",
    r"^Full_Archive\.",
    r"(^|/)identities\.json$",
    r"^Pipeline/config\.json$",
    r"^Pipeline/normalized_exports/",
    r"^Pipeline/logs/",
    r"_chart_cache/(?!\.gitkeep$)",
    r"\.(db|db-wal|db-shm|key)$",
    r"(^|/)msgstore[^/]*$(?<!msgstore_export\.py)",
    r"\.crypt\d*$",
]


def main():
    out = subprocess.run(["git", "ls-files"], capture_output=True, text=True, check=True).stdout
    bad = [f for f in out.splitlines()
           if not f.startswith("sample_data/")
           and not f.endswith("/.gitkeep") and f != ".gitkeep"
           and any(re.search(p, f) for p in FORBIDDEN)]
    if bad:
        print("Refusing: git is tracking files that look like private chat data:\n")
        for f in bad:
            print(f"  {f}")
        print("\nUnstage them (`git rm --cached <file>`) and keep them in your data directory.")
        return 1
    print("OK: no private-looking files are tracked.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
