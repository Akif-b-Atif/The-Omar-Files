# PDF Export — Technical Documentation

Converts `Full_Archive.txt` into a printable, shareable PDF, for anyone
who'd rather read the archive as a document than a plain-text file.

## What it does

`to_pdf.py` reads the archive one line at a time, groups messages under
a date header whenever the date changes, and renders each sender/time
line in bold with the message text below it. WhatsApp's own inline
formatting is carried over: `*bold*`, `_italic_`, and `~strike~` are
rendered as such, and media placeholder lines (`<Media omitted>` and
its variants) are skipped rather than printed as empty entries.

## Setup

This needs `reportlab`, plus a Unicode-capable font file that isn't
included in this project:

```
pip install -r ../../requirements.txt --break-system-packages
```

(That's the one shared `requirements.txt` for every tool under
`Pipeline/Tools/` — arc_analyzer, chat_analyzer, and pdf_export all draw
from it, so installing it once covers all three.)

Download **NotoSans-Regular.ttf** (Google Fonts) and place it in the
shared `Pipeline/Tools/fonts/` folder (not this folder — that font
folder is shared with chat_analyzer's PDF export too, so it only needs
setting up once for both tools). It's not bundled here to keep this
repository small; the script checks for it on startup and explains
where to put it if it's missing.

`run_new_month.py` runs this automatically every month. Run it directly
here only to regenerate the PDF on its own, without running the whole
monthly routine.

## Running it

```
python3 to_pdf.py
```

With no arguments, this reads `Full_Archive.txt` from the project root
and writes `Full_Archive.pdf` at the project root. Both can be
overridden:

```
python3 to_pdf.py path/to/input.txt path/to/output.pdf
```

## Input format

Expects the standard archive line format:

    DD-Mon-YYYY, HH:MM - Sender: message

(Seconds, if present in an older archive, are also accepted — see "Time
precision" in `Pipeline/TECHNICAL.md`.) Any line that doesn't match this
pattern is treated as a continuation of the previous message — correct
for genuine multi-line texts, and also how `[SYSTEM]` / `[UNPARSED]`
tagged lines from the pipeline end up rendered (as part of whatever
message precedes them, since they don't match the pattern either). This
is a read-only formatting tool; it doesn't need to understand every tag
the pipeline produces, just render what's there.
