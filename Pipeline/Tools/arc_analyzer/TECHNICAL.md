# Arc Analyzer — Technical Documentation

Finds "Arcs" (sustained periods of unusually high message frequency),
"Mini-arcs" (smaller/shorter spikes), and "Filler" (everything else) in
`Full_Archive.txt`, then reports stats for each segment and plots the
rolling-average frequency curve with each segment marked.

This is a way of turning "the group was really active for a while
around March" into something concrete: exactly which days, how much
more active than usual, who drove it, and what was actually being
talked about.

## Setup

```
pip install -r ../../requirements.txt --break-system-packages
```

(That's the one shared `requirements.txt` for every tool under
`Pipeline/Tools/` — arc_analyzer, chat_analyzer, and pdf_export all draw
from it, so installing it once covers all three.)

No need to copy `Full_Archive.txt` anywhere — this reads it directly
from the project root by default.

`run_new_month.py` runs this automatically every month. Run it directly
here only to regenerate this report on its own, without running the
whole monthly routine — useful right after tuning the `CONFIG` values
below.

## Running it

```
python3 arc_analyzer.py
```

With no arguments, this reads `Full_Archive.txt` from the project root
and writes `arc_report.txt` and `arc_timeline.png` to `Reports/` at the
project root (created automatically) — the two files meant for regular
reading. `arc_summary.csv` and `arc_summary.json` (the same data,
structured, for further analysis) go into this module's own `data/`
folder instead, since they're supplementary rather than something to
read directly. Any of these can be overridden:

```
python3 arc_analyzer.py path/to/input.txt -o path/to/report_dir --data-dir path/to/data_dir
```

## How segments are detected

1. Messages are bucketed into a daily message count, then smoothed with
   a rolling average (`ROLLING_WINDOW_DAYS`, centered).
2. Local maxima in that rolling curve are found — a day that's the
   highest point within a window of neighboring days
   (`LOCAL_MAX_ORDER_DAYS`) and clears a minimum height
   (`MIN_PEAK_MULTIPLIER` × the whole-archive daily mean).
3. From each peak, the region grows outward in both directions for as
   long as the rolling average stays above a "back to normal" threshold
   (`RETURN_TO_BASELINE_MULTIPLIER` × the mean).
4. Regions that end up close together are merged
   (`MERGE_GAP_DAYS`).
5. Each surviving region is classified as an **Arc** if its peak clears
   `ARC_PEAK_MULTIPLIER` × the mean *and* it lasts at least
   `ARC_MIN_DURATION_DAYS` — otherwise it's a **Mini-arc**.
6. Everything not inside a detected region is **Filler**.

All of these thresholds live in the `CONFIG` class at the top of
`arc_analyzer.py` and are the main thing to tune — the current values
came from trial and error against this archive's actual activity
pattern, so they may need adjusting for a different group's rhythm.

## Per-segment stats

For each segment (Arc, Mini-arc, or Filler), the report includes:

- Duration, message count, average messages/day, peak day.
- **Top contributors** — who sent the most messages in this segment.
- **Distinctive contributors** — who sent a *larger share* of messages
  in this segment than they typically do elsewhere (their share here
  minus their share in the rest of the archive), which surfaces people
  who were unusually central to that particular period even if they
  aren't the group's most talkative overall.

This used to also include a **Keywords** line (words that appeared
disproportionately more often in a segment than in the rest of the
archive). That's been removed — `chat_analyzer`'s own "Arcs &
Mini-arcs" section already runs its full Words & Phrases analysis
separately for every Arc/Mini-arc (see chat_analyzer's TECHNICAL.md),
so a second, cruder word-frequency pass here was pure duplication.
Word/keyword analysis for a given period now lives in exactly one
place: `chat_report.html`/`chat_report.pdf`.

## Naming arcs & mini-arcs

`arc_report.txt` opens with an editable **ARC NAMES** table, one line
per Arc/Mini-arc (Filler periods aren't nameable — they're not
interesting enough on their own to bother), looking like:

```
arc 1: Miniarc-1
  description:
arc 2: Miniarc-2
  description:
arc 3: arc-1
  description:
```

The numbering (`arc 1`, `arc 2`, ...) just counts chronologically
across every Arc and Mini-arc together; the default name after the
colon reflects the segment's own type and position within that type
(`Miniarc-1` is the first Mini-arc, `arc-1` is the first full Arc, even
though it shows up third overall in the example above). Replace the
text after the colon to rename any of them, and fill in the
`description:` line below it if you'd like.

Both the name and description flow straight into `chat_analyzer`'s
report, which builds one self-contained mini-report per Arc/Mini-arc
using whatever's currently in this table — see chat_analyzer's
TECHNICAL.md for details.

Renaming here is safe across reruns: the next time `arc_analyzer.py`
regenerates `arc_report.txt`, it reads the old file first and carries
your custom names/descriptions over, matched to the same Arc/Mini-arc
by its chronological position within its own type. If the *number* of
detected Arcs or Mini-arcs changes between runs (e.g. after tuning a
`CONFIG` threshold), double check the names still line up with the
right period — the matching is positional, not content-aware.

## Output

- `arc_report.txt` — plain-text summary of every segment, with the
  editable ARC NAMES table at the top (`Reports/`).
- `arc_timeline.png` — the rolling-average curve with Arc and Mini-arc
  boundaries marked (`Reports/`). Each boundary is labeled with both
  its chronological label and its current name (e.g. `Arc 1: "Exam
  Season"`), pulled from the same `name` that `arc_report.txt`'s ARC
  NAMES table carries across reruns — a freshly detected segment that
  hasn't been renamed yet just shows its generic default (e.g.
  `Miniarc-3: "Miniarc-3"`) until you edit `arc_report.txt` by hand and
  regenerate.
- `data/arc_summary.csv` / `data/arc_summary.json` — the same segment
  data, structured, for further analysis (this module's own folder).
  Includes whichever name/description each segment had as of this run
  — `chat_analyzer` re-reads `arc_report.txt` directly rather than
  relying on this file, though, so a hand-edited name shows up there
  even without re-running this script.

## Input format

Expects the standard archive line format:

    DD-Mon-YYYY, HH:MM - Sender: message

(Seconds, if present in an older archive, are also accepted.) Lines
that don't match this pattern are treated as a continuation of the
previous message. Lines matching `SYSTEM_MESSAGE_SUBSTRINGS` (group
adds/leaves, subject changes, etc.) are dropped entirely before
analysis — they'd otherwise skew both the daily message counts and the
keyword analysis.
