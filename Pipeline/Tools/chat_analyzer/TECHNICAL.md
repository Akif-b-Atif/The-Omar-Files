# Chat Analyzer — Technical Documentation

Turns `Full_Archive.txt` into a detailed HTML report (with an
interactive search/explorer tab) and a matching shareable PDF.

## 1. Setup

```
pip install -r ../../requirements.txt --break-system-packages
```

(That's the one shared `requirements.txt` for every tool under
`Pipeline/Tools/` — arc_analyzer, chat_analyzer, and pdf_export all draw
from it, so installing it once covers all three.)

Optional: for emoji to render in the PDF (rather than blank boxes),
download **NotoEmoji-Regular.ttf** (Google Fonts) and place it in the
shared `Pipeline/Tools/fonts/` folder — shared with pdf_export's own
font, so it only needs setting up once. Not required; the PDF still
renders fine without it, just without emoji glyphs.

No need to copy `Full_Archive.txt` anywhere — this reads it directly
from the project root by default.

`run_new_month.py` runs this automatically every month. Run it directly
here only to regenerate this report on its own, without running the
whole monthly routine — useful right after editing `chat_config.py`.

## 2. Edit the word lists (do this first)

Open `chat_config.py` and fill in:
- `SWEAR_WORDS` — words counted for the "curses most" stats
- `LAUGH_WORDS` / `LAUGH_REGEX_PATTERNS` — already has generic patterns
  (haha, lol, lmao, hehe, jaja...) that catch stretched-out versions
  like "hahahaha" automatically. Add anything specific to the group.
- `QUESTION_STARTERS` — words that mark a message as a question
- `EXTRA_STOPWORDS` — already filled in with a large list of pronouns,
  articles, prepositions, conjunctions, auxiliary/modal verbs, and
  filler verbs/adverbs (plus their contractions, with and without the
  apostrophe — chat text drops apostrophes constantly). This is what
  keeps "most repeated words" close to nouns-only, since there's no
  real part-of-speech tagger in the pipeline. Add group-specific filler
  words here if you notice junk slipping through.
- Thresholds: `MIN_WORD_LENGTH`, `MIN_PHRASE_LENGTH`, `MIN_REPEAT_COUNT`,
  `TOP_N`, `SIGNATURE_MIN_MESSAGES`, `SIGNATURE_TOP_N_PER_PERSON`,
  `CONVERSATION_GAP_HOURS`, night-owl/early-bird hour ranges.

This can be re-run as many times as needed after editing this file.

## 3. Run it

```
python3 analyze_chat.py
```

Optional flags:
```
python3 analyze_chat.py --input ../../../Full_Archive.txt --outdir ../../.. --min-messages 10
```
`--min-messages` excludes people with very few messages (e.g. someone
who was added/left quickly) from the per-person leaderboards. If nobody
in the archive clears this threshold, the script exits with a clear
message rather than producing a broken report — lower `--min-messages`
or double check `--input`.

On a ~300k message / 2-year, ~12-person archive this takes about a
minute. Most of that time is the phrase-repetition analysis (grouping
every message by its normalized text). Run `python3 analyze_chat.py
--help` any time for the full flag list with current defaults baked in.

### Custom slices: one section, one date range, or specific people

Every flag below can be combined freely. This is the same pipeline as
the full report — it's just fed a smaller dataframe and/or a narrower
set of sections to render.

```
# Only a PDF, only the words & fun-facts sections, full archive
python3 analyze_chat.py --pdf-only --sections words,funfacts

# Only March 2024, only two people, and looser thresholds since a
# one-month / two-person slice has way less data than the full archive
python3 analyze_chat.py --pdf-only \
    --start-date 2024-03-01 --end-date 2024-03-31 \
    --people "Alice Smith,Bob Jones" \
    --min-repeat-count 2 --min-word-length 4 \
    --out-name march_alice_bob

# Full HTML+PDF+JSON, but skip the "last N days" section entirely
python3 analyze_chat.py --sections overview,timing,leaderboards,individuals,words,mentions,funfacts,arcs

# Change the "last N days" window from 30 to 60
python3 analyze_chat.py --last-period-days 60

# Skip the "Arcs & Mini-arcs" section (e.g. arc_analyzer.py hasn't been run yet)
python3 analyze_chat.py --sections overview,timing,leaderboards,individuals,words,mentions,funfacts,lastperiod
```

| Flag | What it does |
|---|---|
| `--sections a,b,c` | Only render these sections (see the list below). Default: `all`. |
| `--start-date YYYY-MM-DD` | Drop messages before this date. |
| `--end-date YYYY-MM-DD` | Drop messages after this date. |
| `--people "Name One,Name Two"` | Drop every message NOT sent by one of these exact sender names — restricts the whole analysis, not just the leaderboards. |
| `--pdf-only` | Skip the HTML report + search JSON, only write the PDF. Faster for one-off custom slices. |
| `--html-only` | Skip the PDF, only write the HTML report + search JSON. |
| `--out-name NAME` | Base filename for the report(s), e.g. `--out-name march_alice_bob` → `march_alice_bob.pdf`. Default `chat_report`. |
| `--min-word-length N` | Override `MIN_WORD_LENGTH` for this run only. |
| `--min-phrase-length N` | Override `MIN_PHRASE_LENGTH` for this run only. |
| `--min-repeat-count N` | Override `MIN_REPEAT_COUNT` for this run only. |
| `--top-n N` | Override `TOP_N` (size of the "most repeated" leaderboards) for this run only. |
| `--signature-min-messages N` | Override `SIGNATURE_MIN_MESSAGES` for this run only. |
| `--signature-top-n N` | Override `SIGNATURE_TOP_N_PER_PERSON` for this run only. |
| `--last-period-days N` | Size of the built-in "last N days" section (default from `LAST_PERIOD_DAYS` in `chat_config.py`, normally 30). |
| `--arc-summary PATH` | Path to arc_analyzer's `arc_summary.json` (default: `../arc_analyzer/data/arc_summary.json`). Only used by the "Arcs & Mini-arcs" section. |
| `--arc-report PATH` | Path to `arc_report.txt` (default: project root), re-read fresh on every run so a hand-edited name/description shows up even without re-running `arc_analyzer.py` first. |

Valid `--sections` values: `overview`, `timing`, `leaderboards`,
`individuals`, `words`, `mentions`, `funfacts`, `lastperiod`, `arcs`, or
`all` (default). The threshold-override flags (`--min-word-length` etc)
only affect the **words/phrases** computation (most-repeated +
signature words/phrases) — they're the same knobs as the matching
constants in `chat_config.py`, just scoped to a single run instead of
editing the file. They apply to the main report; the built-in "last N
days" section and the "Arcs & Mini-arcs" section always use their own
`LAST_PERIOD_*` thresholds regardless (see below), since mixing "CLI
override for the whole run" with "auto-loosened for a smaller slice"
would be confusing to reason about.

The Explorer tab (HTML only) is always included regardless of
`--sections`, since it's a standalone interactive tool, not a static
section — excluding it would just make the interactive report less
useful for no benefit.

## 4. Output

`chat_report.html`, `chat_report.pdf`, and `chat_search_data.json` are
written directly to the project root (or a custom `--outdir`), right
next to `Full_Archive.txt` — unless `--out-name` is set, in which case
the `.html`/`.pdf` use that base name instead (the search JSON is
always `chat_search_data.json`, since the HTML's Explorer tab fetches
that exact filename):
- **`chat_report.html`** — open this in a browser. Has 9 sections:
  Overview, Timing, Leaderboards, Individuals, Words & Phrases,
  Mentions, Fun facts, a **Last N Days** snapshot, an **Arcs &
  Mini-arcs** section (one mini-report per arc_analyzer.py-detected
  period), and a live **Explorer** tab (word/phrase search, date-range
  breakdown, person-vs-person comparison).
- **`chat_search_data.json`** — data file the Explorer tab fetches at
  view-time. **Must stay in the same folder as the HTML file** — this
  is why both land at the project root rather than inside this tool's
  own folder.
- **`chat_report.pdf`** — same content minus the Explorer (PDFs can't
  run JavaScript), styled for printing/sharing. The two "activity
  fingerprint" charts (hourly rhythm, activity over time) each get
  their own full page so they stay readable instead of being squeezed
  together onto one page. The "Last N Days" snapshot is a self-contained
  "Part Two" appended after the main sections, with its own cover, and
  "Arcs & Mini-arcs" follows as "Part Three" — one self-contained
  sub-report with its own cover per arc/mini-arc.

Chart images used to build the HTML/PDF are cached in `_chart_cache/`
next to this script — that folder isn't a report itself, just working
files, and isn't needed once the HTML/PDF exist. Files from the main
report, the "last N days" section, and each arc/mini-arc use different
filename prefixes in that cache (`arc1_`, `arc2_`, ...) so none of them
overwrite each other.

### If the Explorer tab says "could not load data"

Some browsers (mainly Chrome) block a local HTML file from `fetch()`-ing
a local JSON file for security reasons when the HTML file is opened
directly (`file://...`). If that happens, run a tiny local server
instead, from the project root:

```
python3 -m http.server 8000
```
then open **http://localhost:8000/chat_report.html** in a browser.
Firefox usually works fine either way.

## What's computed

**Overall:** total messages, days spanned, active vs silent days, avg
messages/day, median reply gap, total words/characters, media/deleted/
edited counts, plus the top-3 "fun facts" lists described below.

**Timing:** messages per day (full timeline + 7-day rolling average),
by hour of day, by weekday, weekday×hour heatmap, by month.

**Per person:** message count & share, vocabulary size, avg
words/message, longest message, swear/laugh/question rate, shouting
(ALL CAPS) count, exclamation count, top emoji, hourly fingerprint,
night-owl / early-bird %, double-texting rate, "conversation starts"
(revives chat after a silence), tags given/received, first/last
message, activity-over-time timeline. The two small-multiple charts
that show one panel per person (hourly fingerprint, activity over
time) use identical axis ranges for every panel — for the
activity-over-time chart specifically, every panel spans the analyzed
range's full first-day-to-last-day date range (not just that person's
own active window), with any day they didn't message filled in as 0.
That way someone who joined late or went quiet for a stretch shows up
as a flat line at 0 for that period instead of their panel silently
rescaling to start at their own first message.

**Words & phrases:** top `TOP_N` most-repeated words (`MIN_WORD_LENGTH`+
letters, filtered through `EXTRA_STOPWORDS` so the list is close to
nouns-only) and phrases (`MIN_PHRASE_LENGTH`+ letters), each with first
use / last use / who said it most. A "phrase" is a *whole message*, not
an n-gram fragment: two messages count as the same phrase if they're
identical once emojis, punctuation, and capitalization are stripped
(extra whitespace is also collapsed) — so one long message that
happens to repeat a word many times inside itself only ever counts as
ONE occurrence of that phrase, not dozens of overlapping fake repeats.
All thresholds require ≥`MIN_REPEAT_COUNT` occurrences to filter out
noise.

"Signature" words & phrases (ones effectively owned by one person, by
dominance %) are computed **per person** rather than as a single
overall top-N list: every participant with at least
`SIGNATURE_MIN_MESSAGES` total messages gets their own top
`SIGNATURE_TOP_N_PER_PERSON` signature words and top
`SIGNATURE_TOP_N_PER_PERSON` signature phrases, rendered as one
card/table per person.

**Mentions:** who tags others most, who gets tagged most, top tagging
pairs.

**Fun facts:** top 3 (not just the single best) in each category —
busiest days, quietest active days, longest silences, longest active
streaks, longest messages ever, quickest replies (smallest gap between
two *different* senders — a same-sender gap is a double-text, not a
reply), and most media-heavy days — plus the overall media/deleted/
edited totals.

**Last N Days (built-in snapshot, in both HTML and PDF):** the exact
same analysis above (Overview through Fun facts), re-run on just the
most recent `LAST_PERIOD_DAYS` days (default 30, see
`--last-period-days`) of whatever range is being analyzed. Because that
slice naturally has far fewer messages than the full archive, it uses
its own looser versions of every noise threshold —
`LAST_PERIOD_MIN_WORD_LENGTH`, `LAST_PERIOD_MIN_PHRASE_LENGTH`,
`LAST_PERIOD_MIN_REPEAT_COUNT`, `LAST_PERIOD_TOP_N`,
`LAST_PERIOD_SIGNATURE_MIN_MESSAGES`,
`LAST_PERIOD_SIGNATURE_TOP_N_PER_PERSON` in `chat_config.py` — so it
doesn't come back mostly empty the way reusing the full-archive
thresholds on a month of data would. If nobody messaged at all in that
window, the section is silently skipped rather than shown empty.

**Arcs & Mini-arcs (built-in, in both HTML and PDF):** the same
Overview-through-Fun-facts analysis again, but run separately for
*every* Arc and Mini-arc that `arc_analyzer.py` found — not just one
fixed trailing window. Segment boundaries come from arc_analyzer's
`arc_summary.json` (`--arc-summary` to override); each segment's
current name and description are read fresh from `arc_report.txt`'s
editable "ARC NAMES" table (`--arc-report` to override) on every run,
so a name you just typed in shows up here even if you haven't re-run
`arc_analyzer.py` since. Like the "Last N Days" snapshot, each
arc/mini-arc is a much smaller slice than the full archive, so this
section reuses the exact same `LAST_PERIOD_*` thresholds rather than
its own separate set — they both need identical loosening for the same
reason, so a second set of constants would just be a duplicate knob.
If `arc_report.txt`/`arc_summary.json` don't exist yet (arc_analyzer.py
hasn't been run), or a given arc/mini-arc's window happens to have zero
messages, that part is silently skipped with a log line explaining why,
rather than shown empty or crashing the whole run.

**Explorer (HTML only, interactive):**
- Word/phrase search — enter a word plus optional comma-separated
  variants, get total occurrences, per-person breakdown, first/last use
  with a snippet.
- Date-range explorer — pick two dates, get message counts per person
  for just that window.
- Person comparison — pick two people, see their stats side by side.

## Notes on accuracy

- The parser expects `Full_Archive.txt`'s own format:
  `DD-Mon-YYYY, HH:MM - Sender: Message` (seconds, if present in an
  older archive, are also accepted). It also handles multi-line
  messages, `<Media omitted>`, deleted messages, edited-message tags,
  and WhatsApp system messages (added/left/etc — these are excluded
  from per-person stats but counted separately).
- If the input file's date/time format differs (e.g. 12-hour with
  AM/PM, or `[DD/MM/YY, HH:MM:SS]` brackets — which shouldn't happen if
  it came from `Pipeline/`, but could if a different file is passed via
  `--input`), the regexes at the top of `parsing.py` (`MSG_RE`,
  `DATE_PREFIX_RE`) need a small adjustment.
- Mentions are detected by matching `@Name` against the actual sender
  names (and their first names) in the archive — it won't catch a tag
  typed with a nickname that isn't part of anyone's display name.
- "Nouns-only" word filtering is a curated stopword list
  (`EXTRA_STOPWORDS`), not a real part-of-speech tagger — it's close
  to nouns-only but not perfect (e.g. vague nouns like "thing"/"stuff"
  are kept, and an unusual filler word specific to your group might
  slip through until you add it to the list).
- `--people` filters at the message level (keeps system/join-leave
  messages for streak/silence context, drops every text/media message
  from anyone not listed) — it doesn't just hide other people from the
  leaderboards, it removes them from the analysis entirely, so
  "quickest reply", "mentions", etc. only reflect the selected people
  talking to each other.
- `chat_config.make_profile(**overrides)` is the mechanism behind both
  the CLI threshold flags and the built-in "last N days"/"Arcs &
  Mini-arcs" sections: it snapshots every setting in `chat_config.py`
  into a plain namespace and overrides specific ones, without touching
  the file on disk or affecting other runs.
- Reading/writing the "ARC NAMES" table in `arc_report.txt` is handled
  by `arc_names.py`, which actually lives in the sibling
  `Tools/arc_analyzer/` folder (imported here via `sys.path`) rather
  than being duplicated — arc_analyzer.py uses the same module to
  preserve custom names across its own reruns.
