# Contributing

Thanks for taking a look. This project started as a personal tool for
archiving one specific group chat, so the code assumes WhatsApp's
export format and a fairly small, stable group of people — contributions
that generalize those assumptions are especially welcome.

## Before you open a PR

- **Open an issue first for anything non-trivial** (new export formats,
  new analysis metrics, structural changes to the pipeline) so we can
  talk through the approach before you put time into it.
- **Small fixes** (typos, a parser pattern for a date format
  `common.py` doesn't recognize, a bug fix) can just go straight to a
  PR.

## Where things live

- `Pipeline/scripts/` — the extract → normalize → merge pipeline that
  builds `Full_Archive.txt`. Start with `common.py` if you're adding
  support for a new export format (see "If the parser doesn't match an
  export" in `Pipeline/TECHNICAL.md`).
- `Pipeline/Tools/chat_analyzer/` — the stats report + HTML explorer.
- `Pipeline/Tools/arc_analyzer/` — the activity-spike ("Arc") detector.
- `Pipeline/Tools/pdf_export/` — plain-text archive → PDF.

Each of those has its own `TECHNICAL.md` with implementation detail —
read the relevant one before diving in.

## On WhatsApp changing its export format

WhatsApp has changed the format of its chat exports before, and there's
no guarantee it won't again — a shift in date formatting, timestamp
punctuation, or how a given locale renders AM/PM could all be enough to
break parsing in `common.py`. If that happens, exports that used to
work may suddenly produce unparsed lines or fail to parse at all.

I'll make a best effort to keep the parser current when I notice a
break, but I don't have visibility into every locale or WhatsApp
version, so I can't guarantee I'll catch a given change quickly. If
you hit a parsing failure that traces back to a format change rather
than a bug, a PR with the fix (or even just an issue with a sanitized
sample of the new format, per the privacy note below) is genuinely
appreciated — see "If the parser doesn't match an export" in
`Pipeline/TECHNICAL.md` for where that logic lives and how to extend
it.

## Testing your change

There's no formal test suite yet (an early contribution here would be
very welcome). In the meantime:

1. Use a small, throwaway export — a test group chat with a handful of
   fake messages works fine — rather than real personal data.
2. Run the relevant step of the pipeline directly (`python3
   control.py <command>` from inside `Pipeline/`) and check the output
   by hand.
3. If you touched `common.py`'s parsing patterns, run
   `1_extract_identities.py` and `2_normalize_export.py` against a few
   different export formats to make sure you haven't broken an
   existing one while fixing another.

## A note on privacy

Please don't include real message content, phone numbers, or anyone's
real name in an issue, PR description, or test fixture. Use fake data
(see `Pipeline/identities.example.json` for the shape) — this whole
project exists because message data like that is sensitive, and that
doesn't stop being true just because it's a small example.

## Code style

Nothing enforced by a linter yet — just try to match the style of the
file you're editing (docstrings explaining *why*, not just *what*;
`snake_case.py` filenames; one `TECHNICAL.md` per tool).