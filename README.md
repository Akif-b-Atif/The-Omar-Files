# The Omar Files

A self-hosted pipeline that turns a WhatsApp group chat into a
permanent, searchable, text-only archive — plus a set of analysis
tools that turn that archive into a comprehensive report: who talks the
most, when the group is active, favorite words and running jokes, and
a breakdown of "Arcs" — the specific stretches of time the group's
activity spiked, and why.

This repo is the generic version of a tool I built for my own group
chat. The docs below explain how to point it at yours.

## Why this exists

I'm in a group chat with the same five or six friends that's been
running since 2024, north of 300,000 messages at this point, covering
years of everyone's interests, inside jokes, and phases of life. Only
one person in the group — the person this repo is named after — had
messages going all the way back to day one, sitting in his phone's
local backup. It occurred to me that if he ever lost that phone,
switched apps, or just tapped the wrong button, an entire shared
history would be gone for good, for all of us, with no way to get it
back. The data hoarder in me wouldn't allow for that.

WhatsApp's own export feature wouldn't help: at the time, it capped a
text export at the most recent ~45,000 messages, nowhere near enough
for a chat that size (WhatsApp has since added the ability to pick a
custom date range, but at the time it was only for the latest 45,000 messages).  
So instead I pulled the raw `msgstore.db` out of a Google Drive backup and decrypted it using
[whatsapp-backup-downloader-decryptor](https://github.com/giacomoferretti/whatsapp-backup-downloader-decryptor),
then wrote my own tooling to turn that into a proper, append-only text
archive I could keep extending every month.

That solved the "don't lose it" problem. But once I had a few hundred
thousand timestamped messages sitting in a text file, the data analyst
in me took over — I wanted to actually dig through it.
So I built a set of analysis tools on top of the archive: overall chat
statistics, a search/explorer view, and an "Arc" detector that finds
the group's high-activity periods and lets you name and describe each
one after the fact. Those started as three separate repos I ran
side by side; this project is what happened when I merged them into
one pipeline I could run with a single command every month.

The name is an homage to the friend who unknowingly held our entire
shared history in one local file for years — without that backup
existing at all, none of this would have been possible to recover.

## What it does

- **Archives.** Every message, from everyone, forever — as plain text,
  independent of WhatsApp, your phone, or anyone's account still
  existing. Re-exportable to PDF.
- **Merges incrementally.** Drop in a new month's export and it's
  slotted into the archive by timestamp, deduplicated against what's
  already there, no matter what order files arrive in.
- **Resolves identities.** Phone number changes, renames, multiple
  devices — everything maps back to one canonical person via an
  editable alias table, resolved once and reused everywhere.
- **Analyzes.** Per-person stats, most active times, most repeated
  words and phrases, an interactive HTML report with a live search
  explorer, and a static PDF version of the same.
- **Finds "Arcs."** Detects the stretches of unusually high activity
  automatically, then lets you retroactively name and describe what
  was actually happening during each one — which then shows up as its
  own mini-report.

## Project layout

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full map,
[`docs/MONTHLY_GUIDE.md`](docs/MONTHLY_GUIDE.md) for the short version
of the routine, and [`Pipeline/TECHNICAL.md`](Pipeline/TECHNICAL.md) /
each tool's own `TECHNICAL.md` for implementation detail.
[`docs/README.md`](docs/README.md) is the plain-language version aimed
at someone who just wants to read the finished archive, not run the
pipeline.

Two folders, side by side. This repo is **code only**; everything that
belongs to your chat lives in a separate, private `data/` folder next to it:

```
some-folder/
├── The-Omar-Files/      <- this repo: code, docs, sample data (safe to publish)
│   ├── Pipeline/        <- control.py + every analysis tool
│   ├── sample_data/     <- fake export + identities to try the pipeline risk-free
│   └── docs/
└── data/                <- YOUR chat: its own private git repo, outside this one
    ├── config.json      <- your word lists / thresholds
    ├── identities.json  <- who is who (real names/numbers)
    ├── Full_Archive.txt <- the archive itself
    ├── Raw_Exports/     <- drop each month's WhatsApp export here
    └── Reports/         <- every generated report lands here
```

Because the data folder sits outside the code repo, a stray `git add .`
in here can never pick up your messages. `data/` is a git repo of its own,
so your archive also gets a history: every merge is committed automatically
(never pushed). Keep that repo private, and think twice before pushing it
anywhere you don't control. Custom location? Use `--data-dir PATH` or the
`OMAR_DATA_DIR` environment variable.

## Setting this up for your own chat

1. **Clone the repo and install dependencies.**
   ```
   git clone <this-repo-url>
   cd The-Omar-Files
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r Pipeline/requirements.txt
   ```
   (Merging and normalizing need nothing beyond the standard library;
   the packages are for the reports.)
2. **Create your data folder.**
   ```
   cd Pipeline
   python3 control.py init-data
   ```
   This makes `../data/` (next to the repo folder) with a starter
   `identities.json` and `config.json`, and `git init`s it. Then check
   everything's in order:
   ```
   python3 control.py doctor
   ```
3. **Try it on the sample data first (optional but recommended).**
   `sample_data/` has a small, fake WhatsApp export already shaped to
   produce real Arcs, running jokes, and per-person patterns, so you
   can see the actual reports before touching your own data. See
   [`sample_data/README.md`](sample_data/README.md) for the two-minute
   setup.
4. **Add your people.** Edit `data/identities.json` and list your
   group's actual people. It maps real phone numbers to real names, which
   is exactly why it lives in the private data folder. See "The
   identities.json model" in `Pipeline/TECHNICAL.md`.
5. **Get your first export.** Export the chat from WhatsApp directly
   (Chat → Export chat → Without media), or, for full history beyond
   what WhatsApp's export UI allows, see "Importing from msgstore.db"
   in `Pipeline/TECHNICAL.md` for pulling it from a phone backup.
   Either way, it lands in `data/Raw_Exports/`.
6. **Run it.**
   ```
   python3 control.py your_export.txt
   ```
   This builds `data/Full_Archive.txt` and every report in
   `data/Reports/`, then commits the new state to the data repo. See
   `docs/MONTHLY_GUIDE.md` for the ongoing monthly routine and
   `python3 control.py -h` for every subcommand.
7. **Customize the analysis (optional).** The code ships with neutral
   defaults. Your group's vocabulary and tuning go in `data/config.json`,
   not in the code: extra swear/laugh words, thresholds, how sensitive
   Arc detection is. See `Pipeline/config.example.json` for every option.
   Your members' names are excluded from the word stats automatically,
   straight from `identities.json`.

### Upgrading from the older single-folder layout

If you already have data inside the repo folder (`Raw_Exports/`,
`Full_Archive.txt`, `Pipeline/identities.json`, ...):

```
cd Pipeline
python3 control.py init-data
python3 control.py migrate                       # copies + verifies by checksum
python3 control.py doctor && python3 control.py reports
python3 control.py migrate --remove-originals    # only once you're happy
```

Then move any edits you made to `chat_config.py` / arc settings into
`data/config.json`. Back up the old folder first: it's the only copy until
you've verified the new one.

## What's not in this repo

Anything specific to a real group: raw exports, the merged archive,
reports, the identity/name mapping, caches, and personal word lists all
live in your separate data folder, never in this repo. The code repo's
`.gitignore`, a CI check (`Pipeline/tools_dev/check_no_private_data.py`),
and an optional pre-commit hook all back that up. What's here is the
pipeline itself: the code, the docs, fake `sample_data/`, and template
`identities.example.json` / `config.example.json` files. See the "note on
privacy" at the end of `docs/ARCHITECTURE.md` for the full reasoning.

## Contributing

This started as, and still mostly is, a personal tool — but issues and
PRs are welcome, especially around:

- Support for export formats/date styles `common.py` doesn't recognize
  yet (see "If the parser doesn't match an export" in
  `Pipeline/TECHNICAL.md`)
- Additional analysis metrics in `chat_analyzer` or `arc_analyzer`
- Platforms beyond WhatsApp (Signal, Telegram, Discord, iMessage
  exports would all fit the same "raw export -> normalize -> merge ->
  analyze" shape)

See [`CONTRIBUTING.md`](CONTRIBUTING.md) before opening a PR.

## License

[MIT](LICENSE) — do whatever you want with it.
