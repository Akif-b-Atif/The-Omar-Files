# Architecture

How this whole project fits together: what each folder is for, why it's
laid out this way, and how the pieces connect. `Pipeline/TECHNICAL.md`
and the `TECHNICAL.md` inside each tool under `Pipeline/Tools/` cover
the detail specific to each part; this file is the map.

## Design goals

I built this to work for two different audiences at once:

- **Anyone in the group**, who just wants to read the chat history and
  the reports built from it, and doesn't know or care how they're
  produced. For them, everything that matters is a small, fixed set of
  files sitting at the top level of this project — nothing to dig for.
- **Me**, the one person who maintains it, who needs the machinery
  behind those files to be predictable, safe to re-run, and quick to
  get through every month.

Everything about the layout follows from that split, plus one rule:
**the code and the data never share a folder.** Two folders sit side by
side:

- **`The-Omar-Files/`** (this repo) holds only code, docs and fake sample
  data. It's safe to publish, and it's all anyone needs to build their own
  archive.
- **`data/`** holds everything that belongs to a real chat: the archive,
  every raw export, `identities.json`, the generated reports, caches and
  personal settings. It's its own private git repo.

Because `data/` is outside the code repo's folder, nothing in it can be
swept up by a `git add .` over here, which is a stronger guarantee than a
`.gitignore` (which only works until the day someone edits it). It also
means the archive has real version history of its own: every successful
merge is committed to `data/` automatically.

## Top-level layout

```
some-folder/
├── The-Omar-Files/          <- this repo: CODE ONLY
│   ├── README.md                <- overview + setup
│   ├── docs/                    <- this file, MONTHLY_GUIDE.md, plain-language README
│   ├── sample_data/             <- fake export + identities to try the pipeline
│   └── Pipeline/                <- all the code (see below)
└── data/                    <- YOUR chat: private, separate git repo
    ├── config.json              <- your word lists / thresholds (optional)
    ├── identities.json          <- name/alias directory (source of truth for names)
    ├── Full_Archive.txt         <- THE archive. Everyone reads this one.
    ├── Raw_Exports/             <- where each month's raw export goes; kept forever
    ├── normalized_exports/      <- derived, mid-pipeline (not in git)
    ├── logs/merge_log.json      <- history of every merge run
    ├── Reports/                 <- every generated report lands here (not in git)
    │   ├── Full_Archive.pdf         <- the archive, as a PDF
    │   ├── chat_report.html         <- chat statistics report (interactive)
    │   ├── chat_report.pdf          <- chat statistics report (static)
    │   ├── chat_search_data.json    <- data file chat_report.html's search needs
    │   │                                (must stay next to it — see below)
    │   ├── arc_report.txt           <- high-activity-period report (names/descriptions
    │   │                                editable at the top — see "ARC NAMES" in it)
    │   └── arc_timeline.png         <- chart accompanying arc_report.txt
    └── .cache/                  <- chart images, arc summary data (not in git)
```

`Pipeline/omar_paths.py` is the one module that knows where the data
directory is: `--data-dir`, else `$OMAR_DATA_DIR`, else a sibling folder
named `data`. It refuses a location inside this repo's folder. Every
script and tool gets its paths from it, so there's no hardcoded
`../../Raw_Exports` anywhere.

Every finished report sits in `Reports/`, as a flat file, rather than
nested any deeper. `Full_Archive.txt` sits at the top of the data folder
because it's the actual deliverable this project exists to produce and
protect, not something derived from running a tool.
`chat_search_data.json` looks like an odd one out inside `Reports/`
since it's not really "a report" on its own, but the Explorer tab in
`chat_report.html` fetches it by a relative path at view-time, so it
has to live in the same folder as the HTML file or that tab breaks —
that's a hard technical requirement, not a choice.

## Raw_Exports/ (in the data folder)

Where I drop each month's WhatsApp export. This is the only folder I
need to open by hand on a normal month, besides `Pipeline/` itself to run
the update script.

Raw exports are never edited or deleted once they're in here — they're
the ground truth. If anything downstream ever has a bug, the archive
can be rebuilt from these plus `identities.json`. Everything derived
(`normalized_exports/`, `Reports/`, `.cache/`) is kept out of the data
repo's git history for exactly that reason.

## Pipeline/

The code: the control panel, path/config handling, the
extract/normalize/merge scripts, and the code behind every report. It holds
no chat data of any kind.

```
Pipeline/
├── control.py                  <- the control panel: update / merge / pdf / chat / arc / reports / init-data / migrate / doctor
├── omar_paths.py               <- where the data directory is; init-data, auto-commit, migrate
├── TECHNICAL.md                <- full technical detail for the archive pipeline
├── requirements.txt            <- dependencies for the report tools under Tools/
├── requirements-dev.txt        <- the above + pytest
├── identities.example.json     <- template for data/identities.json (fake data)
├── config.example.json         <- template for data/config.json (every option, all optional)
├── scripts/                    <- the machinery `control.py` calls
│   ├── common.py                 <- shared parsing/formatting/date logic
│   ├── extract_identities.py     <- one-time bulk name assignment
│   ├── normalize_export.py       <- monthly: raw -> normalized
│   ├── merge_export.py           <- monthly: normalized -> merged into Full_Archive.txt
│   └── msgstore_export.py        <- occasional: msgstore.db -> Raw_Exports/
├── tests/                      <- pytest suite (never touches real data)
├── tools_dev/                  <- repo hygiene scripts (e.g. the tracked-data check CI runs)
└── Tools/                      <- the code behind each report
    ├── fonts/                      <- shared .ttf files (NotoSans, NotoEmoji) for both PDF builders below
    ├── pdf_export/                 <- builds Full_Archive.pdf
    ├── chat_analyzer/               <- builds chat_report.html / chat_report.pdf
    └── arc_analyzer/                 <- builds arc_report.txt / arc_timeline.png
                                        (arc_names.py here is also imported by chat_analyzer)
```

`control.py` lives directly in `Pipeline/`, one folder below the repo
root, so the command I actually run each month is as easy to find as
possible. It's a control panel rather than a single fixed script:
subcommands (`update`, `merge`, `pdf`, `chat`, `arc`, `reports`) give
granular control over which step(s) run, while plain
`python3 control.py <file>` with no subcommand still does the whole
monthly routine in one go. `init-data` / `migrate` / `doctor` handle
setup. See "control.py — the control panel" in `Pipeline/TECHNICAL.md`
for the full command list.

Settings work in two layers. The code ships neutral defaults (word lists
in `chat_analyzer/chat_config.py`, thresholds in `arc_analyzer.py`'s
`CONFIG`); anything specific to my group goes in `data/config.json`,
which overrides them at load time. Member names for the word stats
come from `identities.json` automatically. That's what keeps the
published code generic.

Each tool under `Tools/` reads `Full_Archive.txt` from the data
directory by default and writes its finished report(s) to the data
directory's `Reports/` (created automatically). Anything a tool produces
that ISN'T a finished report — chart images used only to build an
HTML/PDF file, supplementary data exports — goes to the data directory's
`.cache/` instead of cluttering `Reports/`. See each tool's own
`TECHNICAL.md` for specifics.

These three tools used to be three separate repositories, each keeping
its own copy of the archive pulled in from the main project. That meant
re-copying files by hand and always risking a stale copy. Now there's
exactly one copy of the archive in this whole project, and everything
that needs it points at the same file.

Being separate repos also left some redundancy behind that's since been
cleaned up:
- Each tool had its own `requirements.txt`, even though `chat_analyzer`
  and `arc_analyzer` needed the same pandas/numpy/matplotlib and
  `pdf_export`/`chat_analyzer` needed the same reportlab. There's now
  one `Pipeline/requirements.txt` covering all three.
- Two of the tools (`pdf_export` and `chat_analyzer`) each separately
  needed a Unicode/emoji-capable `.ttf` font file dropped into their own
  folder, so setting either one up meant hunting down and placing a
  font file, twice, one repo at a time (and the two used slightly
  different filenames for the same idea, another leftover of them never
  having talked to each other). Both now read from one shared
  `Pipeline/Tools/fonts/` folder — a font file only needs to be placed
  once for both PDF builders to find it.

## The "Arcs & Mini-arcs" naming table

`arc_analyzer.py` and `chat_analyzer` are connected by one more thing
beyond the archive itself: `arc_report.txt` opens with an editable
table where each Arc/Mini-arc arc_analyzer.py found can be given a
custom name and description (default: `Miniarc-1`, `arc-1`, etc, in
order). `chat_analyzer` reads that table (fresh, on every run of its
own) to build a labeled mini-report for each one. The logic for
reading/writing that table lives in one place —
`Pipeline/Tools/arc_analyzer/arc_names.py` — imported directly by
`chat_analyzer`'s `analyze_chat.py` rather than copied, so there's a
single source of truth for how a name in that file gets matched back to
the arc/mini-arc it belongs to. See arc_analyzer's `TECHNICAL.md` for
the table's exact format and chat_analyzer's `TECHNICAL.md` for how it
shows up in the report.

## How a message gets from WhatsApp to Full_Archive.txt

1. **Export.** Either export the chat from WhatsApp directly (the
   normal monthly case), or, for a first-time full-history import or a
   recovery, pull it from a phone backup's `msgstore.db` with
   `Pipeline/scripts/msgstore_export.py`. Either way, the result lands
   in `Raw_Exports/` — untouched, kept forever, the ground truth.
2. **Normalize.** `normalize_export.py` reads a raw export and
   produces a version in the data folder's `normalized_exports/` where every
   sender label has been resolved to a canonical name via
   `identities.json`, and every date/time is reformatted to one
   consistent style (see "How dates are resolved" in
   `Pipeline/TECHNICAL.md`) regardless of which format it arrived in.
3. **Merge.** `merge_export.py` compares every message in the
   normalized file against what's already in the archive and inserts
   whatever's genuinely new at the position its own timestamp puts it
   — whether that's after everything else, before everything else, or
   somewhere in a gap in the middle. Nothing already in the archive is
   ever rewritten; this step only ever adds new lines or skips exact
   duplicates.
4. **Reports refresh.** Once the archive itself is updated, every
   report in `Reports/` is regenerated so it stays in sync. `arc`
   runs before `chat` in this step specifically (not just alphabetically)
   since chat_analyzer's "Arcs & Mini-arcs" section depends on
   arc_analyzer's output — see `do_reports()` in `control.py`.

`control.py`'s `update` command (the default when it's called with just
a filename) runs steps 2 through 4 in order, which is why it's the only
command I need each month — while its other subcommands
(`merge`/`pdf`/`chat`/`arc`/`reports`) let me run any one of those
steps on its own when that's all I actually want.

## Naming conventions

A few conventions I kept consistent across every module:

- Python files use `snake_case.py` — no hyphens, so every file could be
  imported as a module if that's ever useful, and so there's one
  consistent naming style everywhere.
- Every tool folder under `Pipeline/Tools/` has the same shape: the
  script(s) and a `TECHNICAL.md`. Dependencies (`requirements.txt`) and
  font files live one level up, shared across every tool, rather than
  duplicated per folder (see above). None of the tool folders keep an
  output folder for finished reports — those always go to `Reports/`
  in the data directory, which is what keeps them all in one visible
  place.
- Every technical document is called `TECHNICAL.md`, written in first
  person, and covers just that one part of the project. Root-level
  documents (`README.md`, `MONTHLY_GUIDE.md`, `ARCHITECTURE.md`) are
  the only ones that speak about the project as a whole.
- Person names are spelled the same way everywhere they appear —
  `identities.json` is the source of truth, and nothing else keeps its
  own list of names (the word-stats filter reads them from
  `identities.json` directly).

## A note on privacy

The actual chat content, the original `msgstore.db`, and every report
built from them are specific to the group this was built for. None of it
lives in this repo's folder at all: it's in the separate `data/` folder
described above. The code repo's `.gitignore` still lists the same
patterns as a safety net, `Pipeline/tools_dev/check_no_private_data.py`
fails CI if git ever tracks anything chat-shaped (it also works as a
pre-commit hook), and `omar_paths.py` refuses a data directory inside this
folder.

`identities.json` lives in `data/`, and deliberately so: it maps real
phone numbers to real names, which is a contacts list, not metadata.
`Pipeline/identities.example.json` is committed instead, with placeholder
names/numbers, and `init-data` copies it into a new data folder to edit
for its own group. Personal word lists and thresholds work the same way
(`config.example.json` here, `config.json` in `data/`).

Keep the data repo private. It contains other people's messages, so
think carefully before pushing it to any remote: a private repo on a
hosting service is still someone else's server. A local backup, or an
encrypted remote, is the safer default.
