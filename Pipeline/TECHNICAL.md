# Pipeline — Technical Documentation

How the archive pipeline works: file formats, date/time handling, the
merge algorithm, and the monthly routine. `control.py` and everything
under `scripts/` is plain Python 3 with no external libraries; only the
report tools under `Tools/` need the packages in `requirements.txt`.

## The files that matter

`Full_Archive.txt` and every report in `Reports/` are the only things
anyone needs to read regularly. They live in the **data directory**, a
separate private folder outside this repo (by default `data/`, next to
the repo's folder; see `omar_paths.py`), never in here. Everything in this
folder is code that produces and protects them. Every "data dir" path
below means that folder.

## Directory layout

```
Pipeline/
├── TECHNICAL.md               <- this file
├── control.py                 <- the control panel: update / merge / pdf / chat / arc / reports / init-data / migrate / doctor
├── omar_paths.py              <- where the data dir is; init-data, auto-commit, migrate, config.json loading
├── identities.example.json    <- template for <data dir>/identities.json
├── config.example.json        <- template for <data dir>/config.json
├── requirements.txt           <- dependencies of the report tools
├── requirements-dev.txt       <- + pytest
├── pytest.ini                 <- test config (registers the `smoke` marker)
├── tests/                      <- pytest suite — see tests/README.md
├── tools_dev/                  <- repo hygiene (tracked-data check used by CI)
├── scripts/
│   ├── common.py                 <- shared parsing/formatting/date logic
│   ├── extract_identities.py     <- one-time bulk name assignment
│   ├── normalize_export.py       <- monthly: raw -> normalized, asks about new people
│   ├── merge_export.py           <- monthly: normalized -> merged into Full_Archive.txt
│   └── msgstore_export.py        <- occasional: msgstore.db -> <data dir>/Raw_Exports/
└── Tools/                      <- one folder per report, see each one's own TECHNICAL.md

<data dir>/                     <- NOT in this repo
├── config.json                 <- your overrides of the generic defaults (optional)
├── identities.json             <- name/alias directory (source of truth for names)
├── Full_Archive.txt            <- the archive
├── Raw_Exports/                <- ground truth, kept forever
├── normalized_exports/         <- each raw export, names normalized, mid-pipeline (derived)
│   ├── 00_initial_port_normalized.txt
│   └── 2026-09_normalized.txt
├── logs/merge_log.json         <- history of every merge run (with a sha256 of each source file)
├── Reports/                    <- every generated report (derived)
└── .cache/                     <- chart images, arc summary data (derived)
```

`control.py` lives directly in `Pipeline/` rather than inside
`scripts/` with the rest of the machinery, so the command I actually
run each month is as easy to find as possible.

## control.py — the control panel

Everything below this section (the merge algorithm, date handling,
identities model, etc.) explains *how* the pipeline works. `control.py`
is *how I run it* — one script, one subcommand per thing I might want
to do, instead of remembering which file under `scripts/` or `Tools/`
does what:

```
python3 control.py                          # refresh all reports, no new export
python3 control.py 2026-09_raw.txt          # full monthly update (bare filename = update)
python3 control.py update 2026-09_raw.txt   # same, spelled out
python3 control.py merge 2026-07_raw.txt 2026-08_raw.txt 2026-09_raw.txt
                                             # merge several missed exports as one
python3 control.py pdf                      # rebuild Reports/Full_Archive.pdf only
python3 control.py arc                      # rebuild Reports/arc_report.* only
python3 control.py chat [--min-messages N]  # rebuild Reports/chat_report.* only (reads Reports/arc_report.txt — run arc first if it needs refreshing too)
python3 control.py reports                  # rebuild pdf+arc+chat, no merge
```

A bare filename anywhere a raw export is expected is looked up
automatically inside `<data dir>/Raw_Exports/` — a relative or absolute path also works if the file is
somewhere else. `merge` (and `update`, when given files) can take more
than one filename in a single call; each is normalized and merged in
turn, so they end up in the archive exactly as if they'd been one
combined export — the merge step in `merge_export.py` places every
message by its own timestamp, so it doesn't matter what order the
files are listed in or which one is chronologically first.

`update` (the default when no subcommand is given) merges any files
it's given — stopping immediately if that fails, since a half-applied
merge should never be left in place silently — then always regenerates
all three reports afterward, in a non-fatal way: one report failing prints a warning and moves on rather
than undoing the archive update or blocking the other reports. Running
`pdf`, `chat`, or `arc` directly, on the other hand, *does* exit
non-zero on failure, since in that case regenerating that one thing is
the entire point of the command — there's nothing else in the same run
for a warn-and-continue to make sense against. `reports` follows the
same standalone rule (fails loudly) but still runs all three regardless
of one failing, so an unrelated failure in one report doesn't stop the
other two from refreshing.

After a successful merge, if the data directory is a git repo (the
`init-data` command makes it one), `control.py` commits the new state
there (`Merge <files>`; never pushed). That's the archive's undo history:
`git -C <data dir> log`, `git -C <data dir> revert ...`. `--no-commit`
skips it, and a failed commit only prints a warning; it never affects the
archive. Derived folders (`normalized_exports/`, `Reports/`, `.cache/`) are
in the data repo's `.gitignore` since they can all be rebuilt.

`--data-dir PATH` (before the command) or `$OMAR_DATA_DIR` choose a
different data directory; `control.py` exports its choice to every script
it launches, so they all agree. A directory inside this repo's own folder
is refused. `init-data` creates the data directory (idempotently, never
overwriting your files) and `migrate` copies an old in-repo layout into it,
verifying each file by sha256 and keeping the originals unless
`--remove-originals` is given.

`control.py doctor` is a separate, standalone check — it doesn't touch
the archive or any report. It verifies Python's version, that every
package in `requirements.txt` is actually importable, where the data
directory is and that it has the expected layout, that `config.json`
parses, that `identities.json` exists, that `Raw_Exports/` has something
in it, whether any chat data is still sitting inside the repo folder
(from the old layout), and that the bundled fonts are present, printing
a fix suggestion next to
anything missing. Worth running right after cloning, or any time
something fails in a way that looks environment-related rather than
data-related. Exits non-zero if anything genuinely failed, so it's safe
to use in a script.

## Tests

`tests/` has a pytest suite: unit tests for `common.py`'s date/time
parsing and `merge_export.py`'s merge/dedup logic, tests for the
data-directory and config handling, plus end-to-end tests that run
`control.py` against `sample_data/` in a throwaway repo copy with its own
sibling `data/` folder and check every promised output file gets written
there (and that nothing lands in the code repo). Run it with
`python3 -m pytest tests/ -v` from inside `Pipeline/` (needs
`requirements-dev.txt`). CI runs it on every push. See
`tests/README.md` for what's covered and what isn't yet.

## Why raw exports are kept forever

Three tiers of files exist for this archive:

- **`<data dir>/Raw_Exports/`** — never edited, never
  deleted. Ground truth. If a script has a bug, everything downstream
  can be regenerated from these plus `identities.json`.
- **`normalized_exports/`** — one file per export, names normalized,
  dates/times standardized, but *not* yet merged/deduplicated against
  the rest of the archive. Useful for checking what a specific month's
  export actually contained without searching the full archive.
- **`<data dir>/Full_Archive.txt`** — the deduplicated
  merge of everything above, in chronological order. The only file
  meant for regular reading.

This is plain text, so the storage cost of keeping all three tiers is
negligible — 300k messages at a generous 150 bytes each is roughly
45MB; keeping raw + normalized + merged copies for years is still well
under a gigabyte. `normalized_exports/` can always be regenerated from
`Raw_Exports/` + `identities.json` by re-running step 2 on each raw
file, so it isn't irreplaceable, but there's no real reason to delete
it either.

## How dates are resolved

Raw exports show up in a lot of different shapes — `2024-12-13`,
`13/12/2024`, `12/13/2024`, `8/4/26`, `19-Jul-2026` — and the same
group's history can genuinely mix sources that don't agree on day/month
order (a phone-backup extraction and a normal WhatsApp export, say).
`common.py`'s `parse_flexible_date()` resolves all of these the same
way, in this priority order:

1. **A textual month name** (`19-Jul-2026`) is unambiguous — no
   guessing involved.
2. **A 4-digit year that comes FIRST** (`2024-12-13`) is treated as
   ISO 8601: the remaining two components are assumed to be
   (month, day), in that order — this is the plain/ISO style this
   project's raw exports and `msgstore_export.py` both use by default,
   so it's tried as the primary interpretation. If treating them that
   way would produce an invalid date (a "month" over 12), the two are
   swapped and retried once — that only matters for a source that
   happens to put a day-first date's year in front, which is rare but
   handled anyway.
3. **A 4-digit year elsewhere in the string, or no 4-digit year at
   all** (a 2-digit year) — the two remaining components need day/month
   disambiguation:
   - if one of them is **greater than 12**, it's unambiguously the
     day (nothing named "month 13" exists) — this alone resolves the
     large majority of real-world dates, regardless of which locale
     wrote them.
   - if **both are ≤12** (genuinely ambiguous — e.g. `04/08/2026`
     could mean 4 August or April 8), the order is decided **once per
     file** by `detect_date_order()`: an export is written by one phone
     in one locale, so a single unambiguous line anywhere in it
     (`13/08/2026` proves day-first, `08/13/2026` proves month-first)
     settles every ambiguous line in the same file. Only a file where
     *every* date is ambiguous (or one that contradicts itself) falls back
     to a default of day-first, which matches the common non-US
     convention. That's the one remaining case where a date can be
     resolved "wrong" with no way to tell from the text alone.

If a date genuinely can't be resolved into a valid calendar date at
all, it's left exactly as written in the output rather than dropped or
guessed — a message is never lost over a date that can't be parsed.

**If a date came out resolved the wrong way** (day and month swapped):
open the archive (`Full_Archive.txt` in the data dir), find the affected line(s), and fix the date by
hand — the archive is plain text, so this is always safe. If it's a
whole raw export that's consistently ambiguous in a way the defaults
above get wrong, that export's messages will need a manual pass; there
isn't a batch "swap day/month" tool since doing that automatically
risks affecting dates that were actually already correct.

## Time precision — seconds are intentionally dropped

`Full_Archive.txt` stores time to the **minute only** (`HH:MM`, no
seconds), even though a `msgstore.db` extraction naturally includes
seconds and a real WhatsApp export doesn't. This is deliberate: two
records of the exact same message from different sources would
otherwise look like different messages purely because of which source
recorded the seconds and which didn't, breaking the exact-text-match
duplicate detection the merge step relies on. Dropping seconds at
normalize time (`common.py`'s `normalize_time()`) keeps every source
directly comparable.

This means two genuinely different messages sent by the same person in
the same minute will show the same timestamp in the archive — this is
expected and not a bug. Two *identical* messages in the same minute
("lol", "lol") produce identical lines; the merge counts copies rather
than treating the archive as a set, so both are kept (see "How the merge
works").

## The identities.json model

One entry per person, listing every label that's ever referred to
them — old phone number, WhatsApp internal ID, saved contact name, an
old contact name from before a number change, whatever a friend's
export happened to save them as:

```json
{
  "identities": [
    {
      "name": "Alex",
      "aliases": [
        "923001234567@s.whatsapp.net",
        "Alex R",
        "Alex (work)",
        "+92 300 1234567"
      ]
    }
  ]
}
```

No separate "phone number" vs "display name" fields. A phone number, a
WhatsApp internal ID, a saved contact name — they're all just aliases
that resolve to the same canonical name. `common.py` treats them
identically: alias in, name out.

Bare-number aliases (just the digits, no `@s.whatsapp.net`/`@lid`
suffix) are also supported and matter specifically for resolving
in-message @mentions — see below. If someone's only stored alias is
their `...@lid` sender ID, an @mention of their plain phone number
won't resolve automatically; add the bare number as an extra alias if
that comes up.

This file rarely needs hand-editing. `extract_identities.py` and
`normalize_export.py` both update it automatically when their
prompts are answered, saving after every answer so nothing is lost if
a run is interrupted partway through.

## @mentions

WhatsApp mentions appear in message text in two shapes:

- `@923001234567` — `@` directly followed by a phone number or LID
  (`msgstore.db` extractions, and people who aren't saved contacts).
- `@<name>` where the name is the contact name saved on the exporting
  phone, wrapped in invisible Unicode directional isolates (`U+2068` /
  `U+2069`). Two phones can save the same person under different names
  (`@SuperAhsan Ali` vs `@Junior Mossad Agent Ahsan`).

During normalization every mention is checked against `identities.json`:
a number matches an alias as `<number>@s.whatsapp.net`, `<number>@lid` or
a bare number; a name (or a formatted phone number such as
`+966 58 371 5010`) matches an alias directly. A match is rewritten to
`@CanonicalName`, so the same message exported from two phones comes out
as identical text and merges as a duplicate. A mention that matches
nothing keeps its label (minus the invisible isolates) and is listed at
the end of the run — add each listed label as an alias and re-run, or
the two copies of that message won't be recognized as duplicates.

Lookups ignore case, emoji variation selectors, Unicode compatibility
forms and WhatsApp's `~ ` prefix for non-contacts (`omar_identities.alias_key`).
Canonical names count as aliases of themselves, and an alias claimed by
two different identities is reported as a warning instead of one silently
overwriting the other.

Only sequences of 7-20 digits directly after an `@` (not preceded by a
letter or digit, so `me@123...` isn't one) are treated as possible
number mentions, so short numbers that happen to follow an `@` (a year, a
small count) are never misread as one.

## Repeated words/phrases: spread across days

"Most repeated" and per-person "signature" words/phrases are filtered and
ranked by how many DIFFERENT DAYS something was said on, not just how many
times, so a burst of spam can't pass for a trademark:

- Every word/phrase tracks the distinct days it was said on, overall and
  per person. Saying something ten times in one day is one entry that day.
  The total count is still tracked and shown (the `Nd` badge next to a
  count is the number of days).
- **Eligibility:** besides `MIN_REPEAT_COUNT`, it must appear on at least
  `MIN_REPEAT_DAYS` days (for signature lists: the *owner* must).
- **Ranking:** the existing logic is untouched (relative frequency vs. a
  generic chat for words; raw count for phrases; dominance for signature
  lists) and is then multiplied by `days / (days + SPREAD_HALF_DAYS)`.
  With the default of 5, one day is worth ~0.17, five days 0.5, thirty
  days ~0.86.
- **Ownership:** whoever says it on the most days owns a signature
  word/phrase (raw count only breaks ties), and `dominance_pct` is their
  share of all (person, day) entries, so spamming can't buy ownership.
- Slices shorter than the settings (the "last N days" window, short arcs)
  scale the day requirements down so they can still produce results.

Both knobs live in `chat_config.py` and can be overridden per run with
`--min-repeat-days` / `--spread-half-days`.

## Preserve-everything policy

Nothing is silently dropped, except blank lines *between* messages (a
blank line inside a multi-paragraph message is part of it and is kept):

- **Media/deleted/call placeholders** — `<Media omitted>`,
  image/video/audio/sticker/GIF/document omitted, "this message was
  deleted", missed calls. These are recognized (via `MEDIA_PATTERNS` in
  `common.py`) but kept in the output like any other message —
  recognizing them just lets `normalize_export.py` report a count in
  its summary.
- **System/group events** — kept, tagged `[SYSTEM]`.
- **Anything in an unrecognized format** — kept verbatim, tagged
  `[UNPARSED - review this line]`. This only happens for a line that
  (a) doesn't match any known message/event pattern, and (b) isn't a
  continuation of an in-progress multi-line message. A line right after
  a real message that doesn't match anything is instead treated as a
  continuation of that message (correct for genuine multi-line texts),
  so an odd line only gets the `[UNPARSED]` tag if it stands alone with
  nothing before it to attach to.

## How the merge works

`merge_export.py` takes a normalized export and merges it into
`Full_Archive.txt` by comparing actual messages, not by looking for a
seam at one end of the file. Concretely:

1. Both the archive and the new file are parsed back into "blocks" —
   one per logical message (a multi-line message's continuation lines
   are part of the same block), each with its own parsed timestamp.
2. Every block in the new file is checked against the blocks already
   in the archive, using **exact text match** — since both files are
   written in the identical normalized format, an exact match reliably
   means "this is the same message." Matching is by *count*: each copy
   of a line already in the archive cancels exactly one copy in the new
   file, so a message that really was sent twice in the same minute is
   kept twice, while a re-export of the same period still adds nothing.
   Matches are skipped.
3. Everything that's genuinely new gets inserted into the archive at
   the position its own timestamp puts it, via a stable chronological
   merge — not just appended to the end.

Because step 3 works by timestamp rather than by direction, the exact
same script handles every case the same way:

- **The normal monthly case** — an export that comes after everything
  currently archived. Every message in it is new; they all land at the
  end.
- **History from before the archive's current start** — e.g. a
  predecessor group chat with the same people, exported separately.
  Every message in it is new; they all land at the beginning. No
  separate script or flag needed — the merge script doesn't need to be
  told which direction a file goes.
- **A gap-filling or partially-overlapping export** — messages land
  wherever their timestamps put them, duplicates get skipped, gaps get
  filled, all in the same pass.

This never rewrites or reformats anything already correct in the
archive — an existing line's text is never touched by this step. It
only ever skips an exact-duplicate new message, or inserts a genuinely
new one, verbatim, wherever its timestamp says it belongs.

**A message with no parseable timestamp at all** (an
`[UNPARSED - review this line]` entry with nothing before it to attach
to) can't be placed chronologically. Rather than guess, these are
appended at the very end of the archive, clearly flagged in the
merge's output and in `logs/merge_log.json`, so they're easy to find
and reposition by hand if needed.

Re-running the merge script on a file that's already been fully merged
is always safe — every message in it will already be accounted for in
the archive, so nothing gets added twice.

The archive is written atomically (a temp file next to it, flushed, then
swapped in with `os.replace`), so a crash or power cut mid-merge leaves
either the old archive or the new one, never a truncated file. Each entry
in `logs/merge_log.json` records a sha256 of the normalized file it merged.

## One-time initial setup

For the very first import (e.g. an original `port.txt`):

1. Put it into `<data dir>/Raw_Exports/`, renamed to `00_initial_port.txt`.
2. Bulk-assign identities for everyone in it:
   ```
   cd scripts
   python3 extract_identities.py <data dir>/Raw_Exports/00_initial_port.txt
   ```
   This asks, one at a time, who each unrecognized sender label
   belongs to.
3. Normalize it:
   ```
   python3 normalize_export.py <data dir>/Raw_Exports/00_initial_port.txt
   ```
   Since everyone was just assigned in step 2, this runs through with
   no further prompts (unless it finds someone step 2 missed).
4. Merge it in — since `Full_Archive.txt` doesn't exist yet at this
   point, this first "merge" just creates it:
   ```
   python3 merge_export.py <data dir>/normalized_exports/00_initial_port_normalized.txt
   ```
5. Open `Full_Archive.txt` (in the data dir) and check it looks
   right.

## Monthly routine

1. Export the chat from WhatsApp.
2. Drop the raw `.txt` into `<data dir>/Raw_Exports/`, named something like
   `2026-09_raw.txt`.
3. From inside `Pipeline/`, run:
   ```
   python3 control.py 2026-09_raw.txt
   ```
   (a bare filename like that is automatically found in
   `<data dir>/Raw_Exports/`, and is treated as `update` — the do-everything
   command — with no need to type the command word)
4. Answer any prompts about new or unrecognized senders.
5. `Full_Archive.txt` now includes everything through this export, and
   every report in `Reports/` is regenerated right after, as the
   last part of the same run.

If a report-regeneration step fails (usually a missing dependency —
see `Pipeline/requirements.txt`, shared by every tool under `Tools/`),
`control.py` prints a warning and keeps going; the archive update from
earlier steps already happened by that point and isn't affected. Fix
the dependency and re-run just that one report (`python3 control.py
pdf`, `arc`, or `chat` — see "control.py — the control panel" above,
and run `arc` before `chat` if both need re-running, since `chat`'s
"Arcs & Mini-arcs" section reads `arc`'s output), or just let it catch
up next month.

(Also documented, in shorter form, in `MONTHLY_GUIDE.md` at the project
root.)

## Importing from msgstore.db

`msgstore_export.py` covers the case where I have a phone backup's
`msgstore.db` (WhatsApp's own SQLite database) rather than a WhatsApp
`.txt` export — for a first-time full-history import, or to recover an
export if one's ever lost. It isn't part of the monthly routine; the
normal month-to-month source is a real WhatsApp export.

```
cd scripts
python3 msgstore_export.py path/to/msgstore.db "Exact Group Name"
```

This writes into `<data dir>/Raw_Exports/`, auto-named from the group name, in
the plain/ISO format both this project's raw exports and `common.py`'s
default parsing expect:

    2024-12-13 03:17:33 Bob Jones: No wait

— so the result goes through `normalize_export.py` /
`control.py` exactly like any other raw file (seconds are dropped
at normalize time, same as any other source — see "Time precision"
above). Pass `--output` to write somewhere else instead, or
`--owner-name` to change the label used for the phone owner's own
messages (the database leaves those with no sender ID; default is
`Me`).

## If the parser doesn't match an export

`common.py` currently handles three line structures, each accepting any
common date separator/order (see "How dates are resolved" above):

- Plain/ISO style (the default): `2024-12-13 03:17:33 Sender: message`
- Standard WhatsApp Android export: `12/08/2024, 14:23 - Sender: message`
- Standard WhatsApp iPhone export: `[12/08/2024, 14:23:05] Sender: message`

If a file parses to very few or zero messages,
`warn_if_suspicious()` in `common.py` prints a warning — both
`extract_identities.py` and `normalize_export.py` check for this
automatically. Fixing it means opening `scripts/common.py` and adding a
new entry to `MSG_LINE_PATTERNS` / `EVENT_LINE_PATTERNS` matching the
export's actual line structure — the date/time portion itself likely
doesn't need changes, since `parse_flexible_date()` already handles
most date shapes. Test on a small trimmed-down copy of a raw file
first, not the full multi-hundred-thousand-message one, to iterate
faster.

## Backing up the source database

`msgstore.db` itself isn't part of this pipeline — by the time a chat
reaches `Raw_Exports/`, it's already extracted to text. For extra
insurance, a copy of `msgstore.db` can be kept in a separate folder
outside this project (it contains every chat on the phone, not just
one group, plus media references, so it doesn't belong inside a
text-only, single-group archive).
