# The Omar Files

A self-hosted pipeline that turns a WhatsApp group chat into a
permanent, searchable, text-only archive — plus a set of analysis
tools that turn that archive into a ~200-page report: who talks the
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
back.

WhatsApp's own export feature wouldn't help: at the time, it capped a
text export at the most recent ~45,000 messages, nowhere near enough
for a chat that size (WhatsApp has since added the ability to pick a
custom date range, but that came later). So instead I pulled the raw
`msgstore.db` out of a Google Drive backup and decrypted it using
[whatsapp-backup-downloader-decryptor](https://github.com/giacomoferretti/whatsapp-backup-downloader-decryptor),
then wrote my own tooling to turn that into a proper, append-only text
archive I could keep extending every month.

That solved the "don't lose it" problem. But once I had a few hundred
thousand timestamped messages sitting in a text file, the data hoarder
in me couldn't leave it at that — I wanted to actually dig through it.
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

```
The-Omar-Files/
├── Raw_Exports/         <- drop each month's WhatsApp export here
├── Pipeline/            <- the code: control.py + every analysis tool
├── sample_data/         <- fake export + identities to try the pipeline risk-free
└── docs/                <- README/architecture/guide for this repo
```

## Setting this up for your own chat

1. **Clone the repo and install dependencies.**
   ```
   git clone <this-repo-url>
   cd The-Omar-Files
   pip install -r Pipeline/requirements.txt --break-system-packages
   ```
2. **Try it on the sample data first (optional but recommended).**
   `sample_data/` has a small, fake WhatsApp export already shaped to
   produce real Arcs, running jokes, and per-person patterns, so you
   can see the actual reports before touching your own data. See
   [`sample_data/README.md`](sample_data/README.md) for the two-minute
   setup.
3. **Create your identity file.** Copy the template and add your
   group's actual people:
   ```
   cp Pipeline/identities.example.json Pipeline/identities.json
   ```
   `Pipeline/identities.json` is gitignored on purpose — it maps real
   phone numbers to real names, so it should never leave your machine.
   See "The identities.json model" in `Pipeline/TECHNICAL.md`.
4. **Get your first export.** Export the chat from WhatsApp directly
   (Chat → Export chat → Without media), or, for full history beyond
   what WhatsApp's export UI allows, see "Importing from msgstore.db"
   in `Pipeline/TECHNICAL.md` for pulling it from a phone backup.
   Either way, it lands in `Raw_Exports/`.
5. **Run it.**
   ```
   cd Pipeline
   python3 control.py your_export.txt
   ```
   This builds `Full_Archive.txt` at the project root and every report
   alongside it. See `docs/MONTHLY_GUIDE.md` for the ongoing monthly
   routine and `Pipeline/control.py -h` for every subcommand.
6. **Customize the analysis (optional).** `Pipeline/Tools/chat_analyzer/chat_config.py`
   controls what counts as a swear word, a laugh, a question, and a
   handful of other tunable thresholds — edit it for your own group's
   vocabulary. It also lists common first names to exclude from
   word-frequency stats (otherwise the "most repeated words" leaderboard
   is just whoever gets @-mentioned most); update that list for your
   own group too.

## What's not in this repo

Everything specific to the actual group I built this for — the raw
exports, the merged archive, every generated report, the identity/name
mapping, and the cached analysis data — is excluded via `.gitignore`.
What's here is the pipeline itself: the code, the docs, and a fake
`identities.example.json` to get a new group started. See the "note on
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
