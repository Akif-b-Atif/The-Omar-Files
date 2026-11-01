#!/usr/bin/env python3
"""
control.py  ("group chat" control panel)
------------------------------------
One command-line tool with a subcommand for every step of the pipeline,
so you're never stuck running raw scripts by hand. Run it from inside
this `Pipeline/` folder (or call it by path from anywhere).

    python3 control.py <command> [args]

COMMANDS

  update [file ...]     THE DEFAULT. Do everything. If you give it one
                         or more raw export filenames, it normalizes +
                         merges each one into Full_Archive.txt, then
                         (whether you gave files or not) regenerates
                         every report: Reports/Full_Archive.pdf,
                         Reports/chat_report.*, Reports/arc_report.*.
                         With no files, it just refreshes all the
                         reports from the archive as it stands. This
                         is the old monthly routine, plus the
                         "no files = just refresh reports" convenience.

  merge  file [file...] Normalize + merge one or more raw exports into
                         Full_Archive.txt. Nothing else runs. Give it
                         several files at once and they're merged in
                         one after another, ending up in the archive
                         exactly as if they'd been one combined export
                         — merging is chronological and dedupes by
                         exact text, so it doesn't matter what order
                         you list them in.

  pdf                    Regenerate Reports/Full_Archive.pdf only.

  chat  [--min-messages N]
                         Regenerate Reports/chat_report.html /
                         Reports/chat_report.pdf /
                         Reports/chat_search_data.json only. Its "Arcs
                         & Mini-arcs" section reads whatever
                         Reports/arc_report.txt / arc_summary.json
                         currently exist — run `arc` first (or just
                         use `update`/`reports`, which already run
                         them in the right order) if you want that
                         section to reflect the current archive rather
                         than a stale prior run.

  arc                    Regenerate Reports/arc_report.txt /
                         Reports/arc_timeline.png only.

  reports [--min-messages N]
                         Regenerate all three reports above (pdf, arc,
                         chat — in that order, since chat's "Arcs &
                         Mini-arcs" section depends on arc's output)
                         without touching the archive itself —
                         handy after hand-editing Full_Archive.txt, or
                         after tweaking chat_config.py / arc_analyzer
                         settings and wanting a fresh look without a
                         new export.

  init-data              Create your data directory (the private folder
                         that holds your exports, archive, identities,
                         reports and config.json, kept OUTSIDE this
                         repo -- see "WHERE YOUR DATA LIVES" below),
                         with a starter identities.json / config.json,
                         and `git init` it. Safe to re-run.

  migrate [--remove-originals]
                         One-time move from the OLD layout (data inside
                         this repo's folder) into the data directory.
                         Copies, verifies every file by checksum, and
                         leaves the originals alone unless you add
                         --remove-originals.

  doctor                 Sanity-check your setup before you run
                         anything else: Python version, whether every
                         package in requirements.txt is installed,
                         where the data directory is and what's in it,
                         whether config.json parses, and whether the
                         fonts pdf_export/chat_analyzer need are
                         present. Prints a fix suggestion next to
                         anything that's missing rather than just
                         failing later, mid-pipeline, with a stack
                         trace. Exits non-zero if anything's missing so
                         it's CI/script-friendly.

WHERE YOUR DATA LIVES

  Not in this repo. The data directory is, in priority order:
      --data-dir PATH   (before the command: control.py --data-dir ~/x merge ...)
      $OMAR_DATA_DIR
      ../data           (a folder named "data" next to this repo's folder)
  After every successful merge, if that folder is a git repo, the new
  state is committed to it automatically (never pushed). Add --no-commit
  to `update`/`merge` to skip that.

FILE ARGUMENTS

  Anywhere a raw export filename is expected, just give the bare name
  — it's looked up automatically inside <data dir>/Raw_Exports/:

      python3 control.py merge 2026-09_raw.txt

  A relative or absolute path also works if the file lives elsewhere.

CALLING WITH NO SUBCOMMAND

  If you just run `python3 control.py` or `python3 control.py 2026-09_raw.txt`
  (a bare filename or list of filenames, no command word), that's
  treated as `update` — so the one thing to remember, if you don't
  want to remember anything else, is:

      python3 control.py 2026-09_raw.txt

EXAMPLES

  python3 control.py                          # refresh all reports, no new export
  python3 control.py 2026-09_raw.txt          # full monthly update (= update)
  python3 control.py update 2026-09_raw.txt   # same as above, spelled out
  python3 control.py merge 2026-07_raw.txt 2026-08_raw.txt 2026-09_raw.txt
                                          # catch up on 3 missed months at once
  python3 control.py pdf                      # just rebuild the PDF archive
  python3 control.py chat                     # just rebuild the chat stats report
  python3 control.py chat --min-messages 25   # same, with a higher cutoff
  python3 control.py arc                      # just rebuild the arc report
  python3 control.py reports                  # rebuild pdf+chat+arc, skip merging
  python3 control.py doctor                   # sanity-check your setup
  python3 control.py init-data                # first-time setup of ../data
  python3 control.py migrate                  # move old in-repo data into ../data
"""
import os
import sys
import argparse
import importlib
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import omar_paths  # noqa: E402

PIPELINE_DIR = omar_paths.PIPELINE_DIR
REPO_ROOT = omar_paths.REPO_ROOT
SCRIPTS_DIR = PIPELINE_DIR / "scripts"
TOOLS_DIR = omar_paths.TOOLS_DIR
FONTS_DIR = omar_paths.FONTS_DIR

# Data-directory paths are resolved in main() once --data-dir / $OMAR_DATA_DIR
# are known, then exported so every step control.py launches agrees on them.
PATHS = None

KNOWN_COMMANDS = {"update", "merge", "pdf", "chat", "arc", "reports", "doctor",
                  "init-data", "migrate"}
MIN_PYTHON = (3, 8)
REQUIRED_PACKAGES = ["pandas", "numpy", "matplotlib", "reportlab"]
REQUIRED_FONTS = ["NotoSans-Regular.ttf", "NotoEmoji-Regular.ttf"]


# ---------------------------------------------------------------------------
# small shared helpers
# ---------------------------------------------------------------------------

def run_step(label, cmd, required):
    """Run one script. `required=True` stops the whole control.py invocation on
    failure (used for anything that touches the archive itself — merging
    should never silently half-happen). `required=False` prints a warning
    and keeps going (used for report-regeneration steps, where one report
    failing — usually a missing dependency — shouldn't block the others or
    undo an archive update that already happened)."""
    print(f"\n=== {label} ===")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        if required:
            sys.exit(f"\n{label} failed. Stopping here — see the error above.")
        else:
            print(f"\n[WARNING] {label} failed (see above). Check the tool's "
                  f"TECHNICAL.md (dependencies installed?) and re-run it "
                  f"directly once fixed — e.g. `python3 control.py pdf`.")
    return result.returncode == 0


def resolve_export_path(arg):
    """A bare filename (no path separator) is looked up inside
    <data dir>/Raw_Exports/ automatically. Anything else (a relative or absolute
    path) is used exactly as given."""
    given = Path(arg)
    if given.exists():
        return given.resolve()
    if "/" not in arg and "\\" not in arg:
        candidate = PATHS.raw_exports / arg
        if candidate.exists():
            return candidate.resolve()
    return None


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------

def do_merge_one(raw_arg):
    """Normalize + merge a single raw export. Exits on failure (required
    step — see run_step)."""
    raw_path = resolve_export_path(raw_arg)
    if raw_path is None:
        sys.exit(f"Could not find '{raw_arg}' as given, or inside {PATHS.raw_exports}.")

    run_step(
        f"Normalizing {raw_path.name}",
        [sys.executable, str(SCRIPTS_DIR / "normalize_export.py"), str(raw_path)],
        required=True,
    )

    normalized_name = raw_path.stem.replace("_raw", "") + "_normalized.txt"
    normalized_path = PATHS.normalized / normalized_name

    run_step(
        f"Merging {normalized_name} into Full_Archive.txt",
        [sys.executable, str(SCRIPTS_DIR / "merge_export.py"), str(normalized_path)],
        required=True,
    )
    return raw_path.name


def do_merge(files, commit=True):
    if not files:
        sys.exit("merge needs at least one raw export filename, e.g.:\n"
                  "  python3 control.py merge 2026-09_raw.txt")
    merged_names = [do_merge_one(raw_arg) for raw_arg in files]
    print(f"\nMerged {len(files)} export(s) into {PATHS.archive}.")
    if commit:
        _ok, note = omar_paths.commit_data("Merge " + ", ".join(merged_names))
        print(f"Data repo: {note}")


def do_pdf(required=True):
    return run_step(
        "Regenerating Reports/Full_Archive.pdf",
        [sys.executable, str(TOOLS_DIR / "pdf_export" / "to_pdf.py"),
         str(PATHS.archive), str(PATHS.reports / "Full_Archive.pdf")],
        required=required,
    )


def do_chat(min_messages=None, required=True):
    cmd = [sys.executable, str(TOOLS_DIR / "chat_analyzer" / "analyze_chat.py"),
           "--outdir", str(PATHS.reports),
           "--arc-report", str(PATHS.reports / "arc_report.txt")]
    if min_messages is not None:
        cmd += ["--min-messages", str(min_messages)]
    return run_step("Regenerating Reports/chat_report.html / Reports/chat_report.pdf",
                     cmd, required=required)


def do_arc(required=True):
    return run_step(
        "Regenerating Reports/arc_report.txt / Reports/arc_timeline.png",
        [sys.executable, str(TOOLS_DIR / "arc_analyzer" / "arc_analyzer.py"),
         "--outdir", str(PATHS.reports)],
        required=required,
    )


def do_reports(min_messages=None, required=False):
    """Regenerate all three reports. Non-fatal by default (`required=False`).
    `arc` runs before `chat`, not just alphabetically: chat_analyzer's
    "Arcs & Mini-arcs" section reads arc_analyzer's arc_report.txt /
    arc_summary.json, so those need to be current before chat_analyzer
    runs for that section to reflect this run's archive rather than
    whatever was left over from the last one. `pdf` (the plain-text
    archive export) has no such dependency and can run any time."""
    do_pdf(required=required)
    do_arc(required=required)
    do_chat(min_messages=min_messages, required=required)


def do_update(files, min_messages=None, commit=True):
    if files:
        do_merge(files, commit=commit)
    else:
        print("No export file given — refreshing reports from the archive as it stands.")

    # Once the archive is settled (whether or not it just changed), refresh
    # every report. Non-fatal: a report failing never undoes a merge.
    do_reports(min_messages=min_messages, required=False)

    print("\nAll done.")
    print(f"Archive: {PATHS.archive}")
    print(f"Reports (in {PATHS.reports}): Full_Archive.pdf, "
          "chat_report.html, chat_report.pdf, arc_report.txt, arc_timeline.png")


def do_init_data(init_git=True):
    for line in omar_paths.init_data_dir(init_git=init_git):
        print(f"  {line}")
    print(f"\nNext: put your first WhatsApp export in {PATHS.raw_exports}, then run\n"
          f"  python3 control.py <that_file>.txt\n"
          f"(or try the bundled sample first -- see sample_data/README.md).")
    return True


def do_migrate(remove_originals=False):
    print(f"Migrating old in-repo data into {PATHS.root}\n")
    lines, ok = omar_paths.migrate_legacy(remove_originals=remove_originals)
    print("\n".join(lines))
    if ok:
        print("\nYour personal word lists / thresholds (if you edited "
              "chat_config.py or arc_analyzer.py's CONFIG before) don't move "
              "automatically: put them in "
              f"{PATHS.config.name} -- see Pipeline/config.example.json.")
    return ok


def do_doctor():
    """Checks the things that would otherwise fail loudly (and later,
    mid-pipeline) rather than up front: Python version, dependencies,
    the data directory and what's in it, config.json, and the bundled
    fonts. Prints a PASS/WARN/FAIL line for each check plus a one-line
    fix where relevant, and returns True only if nothing FAILed (WARNs
    are fine -- e.g. an empty Raw_Exports/ is normal on a fresh setup)."""
    print("=== control.py doctor ===\n")
    all_ok = True

    def ok(msg):
        print(f"  [OK]   {msg}")

    def warn(msg, fix=None):
        print(f"  [WARN] {msg}")
        if fix:
            print(f"         -> {fix}")

    def fail(msg, fix=None):
        nonlocal all_ok
        all_ok = False
        print(f"  [FAIL] {msg}")
        if fix:
            print(f"         -> {fix}")

    # --- Python version ---
    if sys.version_info[:2] >= MIN_PYTHON:
        ok(f"Python {sys.version.split()[0]} (>= {'.'.join(map(str, MIN_PYTHON))} required)")
    else:
        fail(f"Python {sys.version.split()[0]} is older than the "
             f"{'.'.join(map(str, MIN_PYTHON))} this pipeline expects.",
             fix="Install a newer Python 3 and re-run with it.")

    # --- Dependencies (only needed for the Tools/ scripts, not
    # scripts/*.py -- see requirements.txt) ---
    missing = []
    for pkg in REQUIRED_PACKAGES:
        try:
            mod = importlib.import_module(pkg)
            version = getattr(mod, "__version__", "unknown version")
            ok(f"{pkg} installed ({version})")
        except ImportError:
            missing.append(pkg)
    if missing:
        fail(f"missing package(s): {', '.join(missing)}",
             fix="pip install -r Pipeline/requirements.txt  (inside a virtualenv is best)")

    # --- data directory ---
    if PATHS.root.is_dir():
        ok(f"data directory: {PATHS.root}")
    else:
        fail(f"no data directory at {PATHS.root}",
             fix="python3 control.py init-data   (or pass --data-dir PATH / set "
                 f"{omar_paths.ENV_VAR})")
    if PATHS.root.is_dir():
        if omar_paths.is_git_repo(PATHS.root):
            ok("data directory is a git repo (merges get committed automatically)")
        else:
            warn("data directory isn't a git repo, so there's no automatic history "
                 "of your archive.", fix=f"git -C {PATHS.root} init")

        # --- config.json ---
        if PATHS.config.exists():
            try:
                omar_paths.load_user_config()
                ok("config.json parses")
            except omar_paths.DataDirError as e:
                fail(str(e), fix="fix the JSON, or delete it to fall back to defaults")
        else:
            warn("no config.json -- every setting uses its generic default.",
                 fix="cp Pipeline/config.example.json <data dir>/config.json  (optional)")

        # --- identities.json ---
        if PATHS.identities.exists():
            ok("identities.json exists")
        else:
            warn("identities.json doesn't exist yet -- normalize_export.py will "
                 "prompt you to name every sender from scratch on your first real export.",
                 fix="cp Pipeline/identities.example.json <data dir>/identities.json")

        # --- Raw_Exports/ ---
        if PATHS.raw_exports.exists():
            raw_files = [p for p in PATHS.raw_exports.iterdir()
                         if p.is_file() and p.name != ".gitkeep"]
            if raw_files:
                ok(f"Raw_Exports/ has {len(raw_files)} file(s)")
            else:
                warn("Raw_Exports/ is empty -- nothing to merge yet.",
                     fix="Drop a WhatsApp export .txt in there, or try "
                         "sample_data/ first (see sample_data/README.md).")
        else:
            fail("Raw_Exports/ is missing from the data directory.",
                 fix="python3 control.py init-data")

        # --- archive ---
        if PATHS.archive.exists():
            ok("Full_Archive.txt exists")
        else:
            warn("Full_Archive.txt doesn't exist yet -- normal before your first merge.")

        # --- reports directory ---
        if PATHS.reports.exists() and any(PATHS.reports.iterdir()):
            ok("Reports/ has generated reports")
        else:
            warn("Reports/ doesn't have any reports yet -- normal before your first "
                 "`python3 control.py reports` (or `update`).")

    # --- leftovers from the old in-repo layout ---
    legacy = [REPO_ROOT / "Full_Archive.txt", PIPELINE_DIR / "identities.json"]
    legacy += [d for d in (REPO_ROOT / "Raw_Exports", REPO_ROOT / "Reports",
                           PIPELINE_DIR / "normalized_exports")
               if d.is_dir() and any(f.name != ".gitkeep" for f in d.iterdir())]
    legacy = [p for p in legacy if p.exists()]
    if legacy:
        warn("found chat data still inside the code repo's folder: "
             + ", ".join(str(p.relative_to(REPO_ROOT)) for p in legacy),
             fix="python3 control.py migrate")

    # --- fonts (needed by pdf_export and chat_analyzer's PDF report) ---
    missing_fonts = [f for f in REQUIRED_FONTS if not (FONTS_DIR / f).exists()]
    if missing_fonts:
        fail(f"missing font file(s) in {FONTS_DIR.relative_to(REPO_ROOT)}: "
             f"{', '.join(missing_fonts)}",
             fix="These ship with the repo -- re-clone if they're missing.")
    else:
        ok(f"required fonts present in {FONTS_DIR.relative_to(REPO_ROOT)}")

    print()
    if all_ok:
        print("Everything checked out. `python3 control.py <raw_export.txt>` when you're ready.")
    else:
        print("One or more checks failed -- fix those before running the pipeline.")
    return all_ok


# ---------------------------------------------------------------------------
# CLI wiring
# ---------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        prog="control.py",
        description="Control panel for the archive pipeline. Run with no "
                     "arguments (or a bare filename) to update everything.",
    )
    parser.add_argument("--data-dir", metavar="PATH", default=None,
                        help="Where your data lives (default: $OMAR_DATA_DIR, "
                             "else a 'data' folder next to this repo's folder). "
                             "Must come BEFORE the command.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_update = sub.add_parser("update", help="Do everything (the default).")
    p_update.add_argument("files", nargs="*", help="Raw export filename(s), optional.")
    p_update.add_argument("--min-messages", type=int, default=None,
                           help="Passed through to the chat report (default 10).")
    p_update.add_argument("--no-commit", action="store_true",
                           help="Don't auto-commit to the data repo after merging.")

    p_merge = sub.add_parser("merge", help="Normalize + merge export(s) only.")
    p_merge.add_argument("files", nargs="+", help="One or more raw export filenames.")
    p_merge.add_argument("--no-commit", action="store_true",
                          help="Don't auto-commit to the data repo after merging.")

    sub.add_parser("pdf", help="Regenerate Full_Archive.pdf only.")

    p_chat = sub.add_parser("chat", help="Regenerate the chat stats report only.")
    p_chat.add_argument("--min-messages", type=int, default=None,
                         help="Ignore senders with fewer messages than this (default 10).")

    sub.add_parser("arc", help="Regenerate the arc report only.")

    p_reports = sub.add_parser("reports", help="Regenerate pdf+chat+arc, no merge.")
    p_reports.add_argument("--min-messages", type=int, default=None,
                            help="Passed through to the chat report (default 10).")

    p_init = sub.add_parser("init-data", help="Create your data directory (outside this repo).")
    p_init.add_argument("--no-git", action="store_true", help="Don't `git init` it.")

    p_mig = sub.add_parser("migrate", help="Copy data from the old in-repo layout into the data directory.")
    p_mig.add_argument("--remove-originals", action="store_true",
                        help="After each file's copy is verified, delete the original.")

    sub.add_parser("doctor", help="Sanity-check your setup (deps, data dir, config, fonts, ...).")

    return parser


def _pull_data_dir_flag(argv):
    """--data-dir is global, but the "bare filename means update" rule below
    inspects argv[0], so it's extracted first. Returns (value or None,
    remaining argv)."""
    rest, value, i = [], None, 0
    while i < len(argv):
        a = argv[i]
        if a == "--data-dir":
            if i + 1 >= len(argv):
                sys.exit("--data-dir needs a path.")
            value = argv[i + 1]
            i += 2
        elif a.startswith("--data-dir="):
            value = a.split("=", 1)[1]
            i += 1
        else:
            rest.append(a)
            i += 1
    return value, rest


def main():
    global PATHS
    data_dir_flag, argv = _pull_data_dir_flag(sys.argv[1:])
    if data_dir_flag:
        # Exported, so every script/tool control.py launches agrees.
        os.environ[omar_paths.ENV_VAR] = str(Path(data_dir_flag).expanduser())
    try:
        PATHS = omar_paths.get_paths()
    except omar_paths.DataDirError as e:
        sys.exit(str(e))
    os.environ[omar_paths.ENV_VAR] = str(PATHS.root)

    # No subcommand given, or the first token isn't one of the known
    # command words -> treat the whole thing as `update` (the default).
    # This is what makes `python3 control.py 2026-09_raw.txt` and even a bare
    # `python3 control.py` work without spelling out "update".
    if not argv:
        argv = ["update"]
    elif argv[0] not in KNOWN_COMMANDS and argv[0] not in ("-h", "--help"):
        argv = ["update"] + argv

    args = build_parser().parse_args(argv)

    # Everything except init-data / doctor needs the data directory to exist.
    if args.command not in ("init-data", "doctor") and not PATHS.root.is_dir():
        try:
            omar_paths.require_paths()
        except omar_paths.DataDirError as e:
            sys.exit(str(e))

    if args.command == "update":
        do_update(args.files, min_messages=args.min_messages, commit=not args.no_commit)
    elif args.command == "merge":
        do_merge(args.files, commit=not args.no_commit)
    elif args.command == "pdf":
        do_pdf(required=True)
    elif args.command == "chat":
        do_chat(min_messages=args.min_messages, required=True)
    elif args.command == "arc":
        do_arc(required=True)
    elif args.command == "reports":
        do_reports(min_messages=args.min_messages, required=True)
    elif args.command == "init-data":
        sys.exit(0 if do_init_data(init_git=not args.no_git) else 1)
    elif args.command == "migrate":
        sys.exit(0 if do_migrate(remove_originals=args.remove_originals) else 1)
    elif args.command == "doctor":
        sys.exit(0 if do_doctor() else 1)


if __name__ == "__main__":
    main()
