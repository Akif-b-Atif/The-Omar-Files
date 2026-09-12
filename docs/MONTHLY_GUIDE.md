# Monthly Guide

What I do every month to keep the archive up to date. In case I forget.

## Steps

1. Export the group chat from WhatsApp as a `.txt` file.

2. Put it in `Raw_Exports/`, named like:

       2026-09_raw.txt

   (year-month keeps files sorted in order; the exact name doesn't
   matter to the scripts, but I keep it consistent.)

3. Open a terminal in `Pipeline/` and run:

       python3 control.py 2026-09_raw.txt

   A bare filename like that is found automatically in `Raw_Exports/` —
   no need to type the full path. No command word needed either — a
   bare filename (or nothing at all) is always treated as `update`,
   the do-everything command (see "The control panel" below).

4. If it asks about a sender it doesn't recognize (a new member, a
   phone number change, etc.), I answer with:
   - an **existing name**, to add this as another alias for someone
     already in the archive
   - a **new name**, to create a new person
   - **Enter**, to skip for now — their messages get tagged
     `[UNRESOLVED]` and the run continues normally; I'll be asked
     again next time an export includes them

5. Done. `Full_Archive.txt` now includes this month, and every report
   in `Reports/` — `Full_Archive.pdf`, `chat_report.html`,
   `chat_report.pdf`, `arc_report.txt`, `arc_timeline.png` — is
   regenerated automatically as the last part of the same run.

That's the only command I need to remember: `control.py`, run from
inside `Pipeline/`, with no arguments other than the file.

## The control panel

`control.py` is the one script with a subcommand for everything, for
whenever I don't want the *entire* monthly routine — just one piece of
it. All of these are run from inside `Pipeline/`:

| I want to...                                   | Command |
|--------------------------------------------------|---------|
| Do the full monthly update                        | `python3 control.py 2026-09_raw.txt` |
| ...same, spelled out                               | `python3 control.py update 2026-09_raw.txt` |
| Just refresh the reports, no new export            | `python3 control.py` (no args) |
| Only merge a new export in, skip the reports       | `python3 control.py merge 2026-09_raw.txt` |
| Catch up on several missed exports at once, as one | `python3 control.py merge 2026-07_raw.txt 2026-08_raw.txt 2026-09_raw.txt` |
| Only rebuild `Reports/Full_Archive.pdf`             | `python3 control.py pdf` |
| Only rebuild the chat stats report                 | `python3 control.py chat` |
| Only rebuild the arc report                        | `python3 control.py arc` |
| Rebuild pdf + chat + arc together, no merge         | `python3 control.py reports` |

Bare filenames (like `2026-09_raw.txt` above) are always looked up
automatically inside `Raw_Exports/` — a full path also works if the
file lives somewhere else. `merge` accepts more than one filename at
once; they're normalized and merged in one after another and end up in
the archive exactly as if they'd been a single combined export, since
merging places every message by its own timestamp regardless of what
file it came from or what order the files were listed in.

`run_new_month.py` still works exactly as before (it's now a thin
wrapper around `control.py update`) if that's the name I've got
memorized — but `control.py` is the one to reach for going forward,
since it covers every other case too. See `Pipeline/control.py`'s own
docstring (`python3 control.py -h`, or open the file) for the full
rundown, including the `--min-messages` option on `chat`/`reports`.

## Where a new message actually goes

`control.py`'s merge step doesn't just append to the end. It compares every
message in the export against what's already in the archive and adds
only the ones that are genuinely new, each inserted at the position its
own timestamp puts it — whether that's after everything else (the
normal case), before everything else (e.g. history from an older,
related chat), or filling a gap in the middle. I don't need to think
about which direction a file goes; it figures that out on its own.

## If something looks wrong

**A report-regeneration step fails (steps 3-5 of the run)**
The archive itself is already updated by this point and is unaffected
— this just means the PDF or one analysis report wasn't refreshed.
Usually a missing dependency; check the `TECHNICAL.md` for that tool
under `Pipeline/Tools/`, and `Pipeline/requirements.txt` (shared by all
of them), then either re-run just that one report (e.g. `python3
control.py pdf`) or let it catch up next month. If it's `chat` that
failed or needs a rerun and `arc` also changed, rerun `arc` first —
`chat`'s "Arcs & Mini-arcs" section reads `arc`'s output.

**A file parses to 0 messages**
The export's format doesn't match what the scripts expect. See "If the
parser doesn't match an export" in `Pipeline/TECHNICAL.md`.

**A date looks wrong (day and month swapped, wrong year, etc.)**
The normalizer tries to resolve dates in whatever format they're
written, but a date like "03/04/25" is genuinely ambiguous (3 April or
4 March?) with no way to know for certain. See "How dates are resolved"
in `Pipeline/TECHNICAL.md` for exactly how it decides, and how to
correct one by hand if it guessed wrong.

**Lines tagged `[UNRESOLVED]`**
That sender was skipped during normalization. I run
`scripts/2_normalize_export.py` on that raw file again once I know who
they are, or edit `Pipeline/identities.json` by hand.

**Lines tagged `[UNPARSED - review this line]`**
The line didn't match any known format. It's kept as-is rather than
dropped — worth a quick look to see what it actually is.

## Occasional, not monthly

- **Getting a group's full history from a phone backup** (`msgstore.db`)
  instead of a WhatsApp export — see `Pipeline/TECHNICAL.md`, "Importing
  from msgstore.db".
- **Refreshing just one report on its own**, without running the whole
  monthly routine — `python3 control.py pdf` / `chat` / `arc` / `reports`
  (see "The control panel" above). Each tool under `Pipeline/Tools/`
  can still be run directly too, with no arguments needed — see its
  own `TECHNICAL.md` — `control.py` just saves having to know which
  script lives where.

## Questions

See `Pipeline/TECHNICAL.md` for how the whole pipeline works, and
`ARCHITECTURE.md` for how the whole project fits together.
