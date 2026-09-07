#!/usr/bin/env python3
"""
control.py  ("group chat" control panel)
------------------------------------
One command-line tool with a subcommand for every step of the pipeline,
so you're never stuck running raw scripts by hand. Run it from inside
this `Pipeline/` folder.

    python3 control.py <command> [args]

COMMANDS

  update [file ...]     THE DEFAULT. Do everything. If you give it one
                         or more raw export filenames, it normalizes +
                         merges each one into Full_Archive.txt, then
                         (whether you gave files or not) regenerates
                         every report: Full_Archive.pdf, chat_report.*,
                         arc_report.*. With no files, it just refreshes
                         all the reports from the archive as it stands.
                         This is the old run_new_month.py, plus the
                         "no files = just refresh reports" convenience.

  merge  file [file...] Normalize + merge one or more raw exports into
                         Full_Archive.txt. Nothing else runs. Give it
                         several files at once and they're merged in
                         one after another, ending up in the archive
                         exactly as if they'd been one combined export
                         — merging is chronological and dedupes by
                         exact text, so it doesn't matter what order
                         you list them in.

  pdf                    Regenerate Full_Archive.pdf only.

  chat  [--min-messages N]
                         Regenerate chat_report.html / chat_report.pdf
                         / chat_search_data.json only. Its "Arcs &
                         Mini-arcs" section reads whatever arc_report.txt
                         / arc_summary.json currently exist — run `arc`
                         first (or just use `update`/`reports`, which
                         already run them in the right order) if you
                         want that section to reflect the current
                         archive rather than a stale prior run.

  arc                    Regenerate arc_report.txt / arc_timeline.png
                         only.

  reports [--min-messages N]
                         Regenerate all three reports above (pdf, arc,
                         chat — in that order, since chat's "Arcs &
                         Mini-arcs" section depends on arc's output)
                         without touching the archive itself —
                         handy after hand-editing Full_Archive.txt, or
                         after tweaking chat_config.py / arc_analyzer
                         settings and wanting a fresh look without a
                         new export.

FILE ARGUMENTS

  Anywhere a raw export filename is expected, just give the bare name
  — it's looked up automatically inside ../Raw_Exports/:

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
"""
import sys
import argparse
import subprocess
from pathlib import Path

PIPELINE_DIR = Path(__file__).parent
REPO_ROOT = PIPELINE_DIR.parent
SCRIPTS_DIR = PIPELINE_DIR / "scripts"
TOOLS_DIR = PIPELINE_DIR / "Tools"
RAW_EXPORTS_DIR = REPO_ROOT / "Raw_Exports"
NORMALIZED_DIR = PIPELINE_DIR / "normalized_exports"

KNOWN_COMMANDS = {"update", "merge", "pdf", "chat", "arc", "reports"}


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
    Raw_Exports/ automatically. Anything else (a relative or absolute
    path) is used exactly as given."""
    given = Path(arg)
    if given.exists():
        return given.resolve()
    if "/" not in arg and "\\" not in arg:
        candidate = RAW_EXPORTS_DIR / arg
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
        sys.exit(f"Could not find '{raw_arg}' as given, or inside {RAW_EXPORTS_DIR}.")

    run_step(
        f"Normalizing {raw_path.name}",
        [sys.executable, str(SCRIPTS_DIR / "2_normalize_export.py"), str(raw_path)],
        required=True,
    )

    normalized_name = raw_path.stem.replace("_raw", "") + "_normalized.txt"
    normalized_path = NORMALIZED_DIR / normalized_name

    run_step(
        f"Merging {normalized_name} into Full_Archive.txt",
        [sys.executable, str(SCRIPTS_DIR / "3_merge_export.py"), str(normalized_path)],
        required=True,
    )


def do_merge(files):
    if not files:
        sys.exit("merge needs at least one raw export filename, e.g.:\n"
                  "  python3 control.py merge 2026-09_raw.txt")
    for raw_arg in files:
        do_merge_one(raw_arg)
    print(f"\nMerged {len(files)} export(s) into "
          f"{(REPO_ROOT / 'Full_Archive.txt').relative_to(REPO_ROOT)}.")


def do_pdf(required=True):
    return run_step(
        "Regenerating Full_Archive.pdf",
        [sys.executable, str(TOOLS_DIR / "pdf_export" / "to_pdf.py")],
        required=required,
    )


def do_chat(min_messages=None, required=True):
    cmd = [sys.executable, str(TOOLS_DIR / "chat_analyzer" / "analyze_chat.py")]
    if min_messages is not None:
        cmd += ["--min-messages", str(min_messages)]
    return run_step("Regenerating chat_report.html / chat_report.pdf", cmd, required=required)


def do_arc(required=True):
    return run_step(
        "Regenerating arc_report.txt / arc_timeline.png",
        [sys.executable, str(TOOLS_DIR / "arc_analyzer" / "arc_analyzer.py")],
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


def do_update(files, min_messages=None):
    if files:
        do_merge(files)
    else:
        print("No export file given — refreshing reports from the archive as it stands.")

    # Once the archive is settled (whether or not it just changed), refresh
    # every report. Non-fatal: a report failing never undoes a merge.
    do_reports(min_messages=min_messages, required=False)

    print("\nAll done.")
    print(f"Archive: {REPO_ROOT / 'Full_Archive.txt'}")
    print("Reports at the project root: Full_Archive.pdf, chat_report.html, "
          "chat_report.pdf, arc_report.txt, arc_timeline.png")


# ---------------------------------------------------------------------------
# CLI wiring
# ---------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        prog="control.py",
        description="Control panel for the archive pipeline. Run with no "
                     "arguments (or a bare filename) to update everything.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_update = sub.add_parser("update", help="Do everything (the default).")
    p_update.add_argument("files", nargs="*", help="Raw export filename(s), optional.")
    p_update.add_argument("--min-messages", type=int, default=None,
                           help="Passed through to the chat report (default 10).")

    p_merge = sub.add_parser("merge", help="Normalize + merge export(s) only.")
    p_merge.add_argument("files", nargs="+", help="One or more raw export filenames.")

    sub.add_parser("pdf", help="Regenerate Full_Archive.pdf only.")

    p_chat = sub.add_parser("chat", help="Regenerate the chat stats report only.")
    p_chat.add_argument("--min-messages", type=int, default=None,
                         help="Ignore senders with fewer messages than this (default 10).")

    sub.add_parser("arc", help="Regenerate the arc report only.")

    p_reports = sub.add_parser("reports", help="Regenerate pdf+chat+arc, no merge.")
    p_reports.add_argument("--min-messages", type=int, default=None,
                            help="Passed through to the chat report (default 10).")

    return parser


def main():
    argv = sys.argv[1:]
    # No subcommand given, or the first token isn't one of the known
    # command words -> treat the whole thing as `update` (the default).
    # This is what makes `python3 control.py 2026-09_raw.txt` and even a bare
    # `python3 control.py` work without spelling out "update".
    if not argv:
        argv = ["update"]
    elif argv[0] not in KNOWN_COMMANDS and argv[0] not in ("-h", "--help"):
        argv = ["update"] + argv

    args = build_parser().parse_args(argv)

    if args.command == "update":
        do_update(args.files, min_messages=args.min_messages)
    elif args.command == "merge":
        do_merge(args.files)
    elif args.command == "pdf":
        do_pdf(required=True)
    elif args.command == "chat":
        do_chat(min_messages=args.min_messages, required=True)
    elif args.command == "arc":
        do_arc(required=True)
    elif args.command == "reports":
        do_reports(min_messages=args.min_messages, required=True)


if __name__ == "__main__":
    main()
