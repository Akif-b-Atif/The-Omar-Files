# The Omar Files

This is a complete, text-only backup of our group chat, plus a couple of
reports built from it. Every message anyone has sent is saved here as
plain text, permanently — even if someone leaves the group, changes
their number, deletes WhatsApp, or the group itself gets deleted one
day.

## Where to look

Everything anyone actually wants to read sits right here at the top
level of this project:

- **`Full_Archive.txt`** — the whole archive, plain text, oldest message
  first. Open with Notepad, TextEdit, or any text app. Use Ctrl+F
  (Cmd+F on Mac) to search for a name, date, or word.
- **`Full_Archive.pdf`** — the same thing, as a printable/shareable PDF.
- **`chat_report.html`** — an interactive stats report (who talks most,
  when the group's most active, favorite words and phrases, and more).
  Open it in a browser.
- **`chat_report.pdf`** — the same report, as a static PDF.
- **`arc_report.txt`** and **`arc_timeline.png`** — a breakdown of
  periods when the group was unusually active ("Arcs") or had a
  smaller spike ("Mini-arcs"), what drove them, and a chart of activity
  over time. Each one starts out just numbered, but anyone can open
  `arc_report.txt` and give them real names/descriptions (e.g. "Exam
  Season") right at the top of the file — those names then show up in
  `chat_report.html`/`chat_report.pdf`, which include a full mini
  version of the stats report for each Arc/Mini-arc individually.

Messages in `Full_Archive.txt` are listed in this format:

    DD-Mon-YYYY, HH:MM - SenderName: message text

## What's not included

Photos, videos, voice notes, and other attachments aren't stored here.
Where media was shared, a placeholder line like "<Media omitted>"
marks that something was sent, without the file itself. This is a
record of what was said, not a media backup.

## The rest of this project

Everything besides the files listed above is the machinery that builds
and updates all of it — not needed just to read the archive or its
reports.

- **`Raw_Exports/`** — where each month's raw WhatsApp export goes.
- **`Pipeline/`** — all the code: `control.py` (the monthly update
  script and control panel), the identity/name mappings, and the tools
  that build each report.

`ARCHITECTURE.md` explains how all of this fits together. `MONTHLY_GUIDE.md`
is the short version of what I do every month.
