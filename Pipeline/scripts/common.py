"""
common.py — shared helpers for the archive pipeline.
Not run directly. Imported by 1_extract_identities.py, 2_normalize_export.py,
and 3_merge_export.py.

If your exports don't parse correctly, this is the file to fix — see
"If the parser doesn't match an export" in Pipeline/TECHNICAL.md.
"""
import re
import json
from datetime import datetime

# ---------------------------------------------------------------------------
# CONFIG — adjust if your WhatsApp export format differs
# ---------------------------------------------------------------------------

# Standard WhatsApp Android export line looks like:
#   12/08/2024, 14:23 - Omar Khan: Message text
# iPhone exports often look like:
#   [12/08/2024, 14:23:05] Omar Khan: Message text
# The plain/ISO style — no comma, no dash, no brackets — is the default
# both a msgstore.db export and a typical raw export in this project use:
#   2024-12-13 03:17:33 Ali Zaman: No wait
# All patterns are tried, in order (plain style first, since it's the
# default), for every line. The date portion of every pattern below
# accepts any of these separators and any digit count for day/month/year
# (1-2 digit day/month, 2-4 digit year) — see parse_flexible_date() for
# how the actual day/month/year values get resolved out of that.
_DATE = r'(?P<date>\d{1,4}[-/.]\d{1,4}[-/.]\d{1,4}|\d{1,2}-[A-Za-z]{3,9}-\d{2,4})'
_TIME = r'(?P<time>\d{1,2}:\d{2}(?::\d{2})?(?:\s?[APap][Mm])?)'

MSG_LINE_PATTERNS = [
    # Plain/ISO style (the default): "DATE TIME Sender: message"
    {
        'regex': re.compile(rf'^{_DATE}\s{_TIME}\s(?P<sender>[^:]+):\s(?P<msg>.*)$'),
        'prefer_day_first': False,  # a bare "DATE TIME" line is presumed
                                    # ISO/year-first already, so this only
                                    # matters if that assumption is wrong
    },
    # Android style: "DATE, TIME - Sender: message"
    {
        'regex': re.compile(rf'^{_DATE},\s{_TIME}\s-\s(?P<sender>[^:]+):\s(?P<msg>.*)$'),
        'prefer_day_first': True,
    },
    # iPhone style: "[DATE, TIME] Sender: message"
    {
        'regex': re.compile(rf'^\[{_DATE},\s{_TIME}\]\s(?P<sender>[^:]+):\s(?P<msg>.*)$'),
        'prefer_day_first': True,
    },
]

EVENT_LINE_PATTERNS = [
    # Plain/ISO style event line, no "sender:" part at all —
    # e.g. "2025-08-04 09:00:00 Omar added Ahmed". Tried only after every
    # MSG_LINE_PATTERNS above has failed to match, so a normal message
    # line is never miscategorized as an event.
    {
        'regex': re.compile(rf'^{_DATE}\s{_TIME}\s(?P<event>.*)$'),
        'prefer_day_first': False,
    },
    # Android style system/event line: "DATE, TIME - some event text"
    {
        'regex': re.compile(rf'^{_DATE},\s{_TIME}\s-\s(?P<event>.*)$'),
        'prefer_day_first': True,
    },
]

# Lines whose message body matches any of these (case-insensitive substring)
# are recognized as media/deleted/call placeholders. As of the "keep
# everything" policy, these are NOT dropped — they're kept in the archive
# like any other message, just counted separately in the normalize
# script's summary so you know how many there were. This list exists so
# they can be recognized/labeled, not to filter anything out.
MEDIA_PATTERNS = [
    "<media omitted>",
    "image omitted",
    "video omitted",
    "audio omitted",
    "sticker omitted",
    "gif omitted",
    "document omitted",
    "this message was deleted",
    "you deleted this message",
    "missed voice call",
    "missed video call",
]

# WhatsApp shows this instead of a message's real content when the
# message hasn't finished syncing/downloading at export time — usually
# for the oldest few messages visible in a chat at export time. It's not
# the message's actual content, just a temporary stand-in, so it should
# never be treated as a genuinely different message from the real
# content the same (date, time, sender) slot may already have in the
# archive from an earlier export (see is_placeholder_msg / merge logic
# in 3_merge_export.py that uses this).
PLACEHOLDER_PATTERNS = [
    "waiting for this message",
]

# WhatsApp sometimes inserts invisible direction-marker characters around
# the " - " separator, which breaks the regexes above if not stripped.
INVISIBLE_CHARS = ['\u200e', '\u200f', '\ufeff']

# Output date/time format, applied consistently to every parsed message
# regardless of which source format it came from — DD-Mon-YYYY avoids the
# day/month ambiguity of slash-separated dates. Time is deliberately
# stored to the MINUTE only (no seconds): a real WhatsApp export never
# has seconds, but a msgstore.db extraction does, and keeping seconds
# would make two records of the same message look like different
# messages when merging, purely because of which source it came from.
# Dropping seconds at normalize time keeps every source comparable.
OUTPUT_DATE_FMT = '%d-%b-%Y'   # e.g. 04-Aug-2025
OUTPUT_TIME_FMT = '%H:%M'      # e.g. 23:29 — minute precision only

# strptime formats to try for a time string, in order.
TIME_PARSE_FORMATS = ['%H:%M:%S', '%H:%M', '%I:%M:%S %p', '%I:%M %p', '%I:%M%p']

# WhatsApp sometimes uses a narrow no-break space before AM/PM instead of
# a normal space, which breaks strptime unless normalized first.
_ODD_SPACES = ['\u202f', '\u00a0']

MONTH_NAMES = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
}


def _split_date_parts(date_str):
    parts = re.split(r'[-/. ]+', date_str.strip())
    return [p for p in parts if p]


def _validate_ymd(year, month, day):
    if not (1 <= month <= 12):
        return None
    try:
        datetime(year, month, day)
    except ValueError:
        return None
    return year, month, day


def _disambiguate_day_month(a_i, a_v, b_i, b_v, prefer_day_first):
    """Given two (index, value) candidates for day/month (indices are
    their original position in the date string), returns
    (month_index, day_index). Whichever value is >12 is unambiguously
    the day; if both are ambiguous (<=12), falls back to whichever
    component appears first, using prefer_day_first to decide whether
    that first one is the day or the month."""
    if a_v > 12 and b_v <= 12:
        return b_i, a_i
    if b_v > 12 and a_v <= 12:
        return a_i, b_i
    first_i, second_i = (a_i, b_i) if a_i < b_i else (b_i, a_i)
    return (second_i, first_i) if prefer_day_first else (first_i, second_i)


def parse_flexible_date(date_str, prefer_day_first=True):
    """
    Resolves a date string of essentially any reasonable shape —
    YYYY-MM-DD, DD/MM/YYYY, MM/DD/YYYY, D-M-YY, DD-M-YYYY, DD-Mon-YYYY,
    with '-', '/', or '.' as separators — into (year, month, day) ints,
    or returns None if it genuinely can't be resolved into a valid date.

    Disambiguation, in priority order:
      1. A textual month name/abbreviation is unambiguous.
      2. Whichever numeric component is 4 digits is the year. If it's
         the FIRST component (the ISO/"the format I gave" convention,
         e.g. 2024-12-13), the remaining two are assumed to be
         (month, day) in that order, per ISO 8601 — swapped only if
         that assumption produces an invalid date (e.g. a genuine
         month > 12) and swapping fixes it. If the year is elsewhere,
         the remaining two need day/month disambiguation (rule 4).
      3. If no component is 4 digits, a 2-digit year is assumed — in
         the first position only if it can't possibly be a day/month
         (>31), otherwise assumed to be the last component (the
         common short form, e.g. DD-MM-YY).
      4. Between two same-priority day/month candidates: whichever is
         >12 is unambiguously the day. If both are <=12 (genuinely
         ambiguous), `prefer_day_first` decides.
    """
    parts = _split_date_parts(date_str)
    if len(parts) != 3:
        return None

    month_idx = next((i for i, p in enumerate(parts)
                       if p[:3].lower() in MONTH_NAMES), None)

    if month_idx is not None:
        month = MONTH_NAMES[parts[month_idx][:3].lower()]
        others = [i for i in range(3) if i != month_idx]
        vals = {i: parts[i] for i in others}
        year_i = next((i for i in others if len(vals[i]) == 4), None)
        if year_i is None:
            i1, i2 = others
            if len(vals[i1]) >= len(vals[i2]):
                year_i = i1 if int(vals[i1]) > 31 or len(vals[i1]) > len(vals[i2]) else i2
            else:
                year_i = i2
        day_i = others[0] if others[1] == year_i else others[1]
        try:
            year = int(parts[year_i])
            day = int(parts[day_i])
        except ValueError:
            return None
        if year < 100:
            year += 2000
        return _validate_ymd(year, month, day)

    try:
        nums = [int(p) for p in parts]
    except ValueError:
        return None

    four_digit_idxs = [i for i, p in enumerate(parts) if len(p) == 4]

    if four_digit_idxs:
        year_i = four_digit_idxs[0]
        year = nums[year_i]
        others = [i for i in range(3) if i != year_i]
        if year_i == 0:
            # Year-first: assume (month, day) order per ISO 8601 — this
            # is "the format I gave", tried as the default interpretation.
            month_i, day_i = others[0], others[1]
            result = _validate_ymd(year, nums[month_i], nums[day_i])
            if result is not None:
                return result
            # Invalid as month-day (e.g. "month" > 12) — the one case
            # this default gets wrong is a genuinely day-first source
            # that happens to also put the year first; swap and retry.
            month_i, day_i = day_i, month_i
            return _validate_ymd(year, nums[month_i], nums[day_i])
        else:
            a_i, b_i = others
            month_i, day_i = _disambiguate_day_month(
                a_i, nums[a_i], b_i, nums[b_i], prefer_day_first)
        return _validate_ymd(year, nums[month_i], nums[day_i])
    else:
        # 2-digit year.
        year_i = 0 if nums[0] > 31 else 2
        year = nums[year_i] + 2000
        others = [i for i in range(3) if i != year_i]
        a_i, b_i = others
        month_i, day_i = _disambiguate_day_month(
            a_i, nums[a_i], b_i, nums[b_i], prefer_day_first)
        return _validate_ymd(year, nums[month_i], nums[day_i])


def normalize_date(raw_date, prefer_day_first=True):
    """Reformats a date string to OUTPUT_DATE_FMT using
    parse_flexible_date(). If it can't be resolved, the original string
    is returned unchanged rather than raising — a message is never
    dropped just because its date couldn't be reformatted."""
    resolved = parse_flexible_date(raw_date, prefer_day_first=prefer_day_first)
    if resolved is None:
        return raw_date
    year, month, day = resolved
    return datetime(year, month, day).strftime(OUTPUT_DATE_FMT)


def normalize_time(raw_time):
    """Reformats a time string to OUTPUT_TIME_FMT (minute precision,
    24-hour — seconds are intentionally dropped, see the OUTPUT_TIME_FMT
    comment above). Falls back to the original string, unchanged, if it
    can't be parsed."""
    cleaned = raw_time.strip()
    for ch in _ODD_SPACES:
        cleaned = cleaned.replace(ch, ' ')
    for fmt in TIME_PARSE_FORMATS:
        try:
            dt = datetime.strptime(cleaned, fmt)
            return dt.strftime(OUTPUT_TIME_FMT)
        except ValueError:
            continue
    return raw_time


# In-message @mentions look like "@923001234567" — an @ followed by a
# phone number, with no "@s.whatsapp.net"/"@lid" suffix in the visible
# text (that suffix only appears in identities.json aliases). 7-15 digits
# covers real phone numbers while avoiding false positives on short
# numbers like years.
MENTION_RE = re.compile(r'@(\d{7,15})\b')


def resolve_mentions(text, alias_map):
    """Replaces any @<number> mention in text with @<CanonicalName> if the
    number matches a known alias — tried as "<number>@s.whatsapp.net",
    "<number>@lid", or a bare "<number>" alias, in that order. Anything
    that doesn't match a known alias is left exactly as it was — never
    guessed, never dropped."""
    def repl(match):
        digits = match.group(1)
        for candidate in (f"{digits}@s.whatsapp.net", f"{digits}@lid", digits):
            if candidate in alias_map:
                return f"@{alias_map[candidate]}"
        return match.group(0)
    return MENTION_RE.sub(repl, text)


def clean_line(line):
    for ch in INVISIBLE_CHARS:
        line = line.replace(ch, '')
    return line.rstrip('\n')


def is_media_or_deleted(msg_text):
    lowered = msg_text.lower()
    return any(p in lowered for p in MEDIA_PATTERNS)


def is_placeholder_msg(msg_text):
    lowered = msg_text.lower()
    return any(p in lowered for p in PLACEHOLDER_PATTERNS)


def load_identities(path):
    """Returns (full_json_data, alias_map) where alias_map maps
    lowercased alias -> canonical name, for fast lookup."""
    if not path.exists():
        data = {"identities": []}
    else:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    alias_map = {}
    for person in data.get('identities', []):
        canonical = person['name']
        for alias in person.get('aliases', []):
            alias_map[alias.strip().lower()] = canonical
    return data, alias_map


def save_identities(data, path):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def warn_if_suspicious(path, messages, raw_line_count):
    """Prints a loud warning if a non-empty file produced zero (or very
    few) parsed messages — almost always means none of the patterns in
    MSG_LINE_PATTERNS/EVENT_LINE_PATTERNS matched this file's format,
    and it needs a new pattern added rather than silently doing nothing."""
    if raw_line_count == 0:
        return
    if len(messages) == 0:
        print(f"\n*** WARNING: {path} has {raw_line_count} non-empty line(s) "
              f"but 0 were recognized as messages. ***")
        print("This almost always means the file's date/time/sender format "
              "doesn't match any pattern in common.py's MSG_LINE_PATTERNS / "
              "EVENT_LINE_PATTERNS. Open the file, look at a sample line, "
              "and add a matching pattern — see 'If the parser doesn't "
              "match an export' in Pipeline/TECHNICAL.md.\n")
    elif len(messages) < raw_line_count * 0.5:
        print(f"\n*** Note: {path} has {raw_line_count} non-empty line(s) "
              f"but only {len(messages)} were recognized as messages. "
              f"That's a low match rate — worth spot-checking the output. ***\n")


def parse_export(path):
    """
    Parses a raw WhatsApp .txt export (or a msgstore.db extraction) into
    a list of dicts: {date, time, sender, msg, unparsed}
    sender is None for system/event lines (e.g. "X added Y").
    unparsed is True for a line that matched no known pattern and also
    wasn't a continuation of an in-progress message — these are kept
    verbatim rather than dropped; nothing is ever silently discarded.
    Multi-line messages (message bodies containing literal newlines) are
    reassembled into a single entry.
    """
    messages = []
    current = None

    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        for raw_line in f:
            line = clean_line(raw_line)
            if not line.strip():
                continue

            matched = False
            for pat in MSG_LINE_PATTERNS:
                m = pat['regex'].match(line)
                if m:
                    if current:
                        messages.append(current)
                    current = {
                        'date': normalize_date(m.group('date'), pat['prefer_day_first']),
                        'time': normalize_time(m.group('time')),
                        'sender': m.group('sender').strip(),
                        'msg': m.group('msg').strip(),
                        'unparsed': False,
                    }
                    matched = True
                    break
            if matched:
                continue

            for pat in EVENT_LINE_PATTERNS:
                m = pat['regex'].match(line)
                if m:
                    if current:
                        messages.append(current)
                    current = {
                        'date': normalize_date(m.group('date'), pat['prefer_day_first']),
                        'time': normalize_time(m.group('time')),
                        'sender': None,
                        'msg': m.group('event').strip(),
                        'unparsed': False,
                    }
                    matched = True
                    break
            if matched:
                continue

            # Not a new timestamped line -> continuation of the previous
            # (multi-line) message.
            if current:
                current['msg'] += '\n' + line
            else:
                # A line that matches nothing AND isn't a continuation of
                # anything — e.g. junk at the very top of the file, or a
                # format we don't recognize. Never drop it: keep it as
                # its own entry, flagged, so it still ends up in the
                # archive and is easy to spot for a human to review.
                messages.append({
                    'date': None,
                    'time': None,
                    'sender': None,
                    'msg': line,
                    'unparsed': True,
                })

        if current:
            messages.append(current)

    return messages


# ---------------------------------------------------------------------------
# Parsing an already-normalized file (Full_Archive.txt itself, or a
# ../normalized_exports/*.txt file) back into structured blocks. Used by
# 3_merge_export.py to figure out chronological order and duplicates —
# never used to alter any text, only to read it.
# ---------------------------------------------------------------------------

ARCHIVE_LINE_RE = re.compile(
    r'^(?P<date>\d{2}-[A-Za-z]{3}-\d{4}), (?P<time>\d{2}:\d{2}) - (?P<rest>.*)$'
)
_ARCHIVE_DT_FMT = f"{OUTPUT_DATE_FMT} {OUTPUT_TIME_FMT}"
_SENDER_RE = re.compile(r'^(?P<sender>[^:]+):\s')


def extract_slot_key(block_text):
    """
    Given a block's exact archive-format text (as produced by
    parse_normalized_blocks — 'DD-Mon-YYYY, HH:MM - Sender: msg...'),
    returns a (date, time, sender) key identifying "who sent something
    at this timestamp", ignoring the message content itself. Returns
    None for a [SYSTEM] line (no sender) or anything not in the
    expected dated-line format.

    This is intentionally coarser than exact-text matching: two real,
    distinct messages from the same sender in the same minute will
    collide on this key. That's fine for its one use (see
    3_merge_export.py) — recognizing "the archive already has *some*
    content in this slot" so a "waiting for this message" placeholder
    from a re-export doesn't get inserted as a bogus duplicate next to
    the real content that's already archived.
    """
    first_line = block_text.split('\n', 1)[0]
    m = ARCHIVE_LINE_RE.match(first_line)
    if not m:
        return None
    sm = _SENDER_RE.match(m.group('rest'))
    if not sm:
        return None
    return (m.group('date'), m.group('time'), sm.group('sender').strip())


def parse_normalized_blocks(path):
    """
    Parses a file already in the normalized/archive output format
    (produced by 2_normalize_export.py, or Full_Archive.txt itself)
    into a list of blocks:
        {'datetime': datetime object or None, 'text': the block's exact
         original text, verbatim, possibly spanning multiple physical
         lines for a multi-line message}
    This never alters any text — it's purely for figuring out
    chronological order and detecting exact-duplicate messages. Returns
    an empty list if the file doesn't exist (e.g. Full_Archive.txt
    before the very first merge).
    """
    blocks = []
    current_lines = None
    current_dt = None

    def flush():
        nonlocal current_lines, current_dt
        if current_lines is not None:
            blocks.append({'datetime': current_dt, 'text': '\n'.join(current_lines)})
        current_lines = None
        current_dt = None

    if not path.exists():
        return blocks

    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        for raw_line in f:
            line = raw_line.rstrip('\n')
            if not line.strip():
                continue
            m = ARCHIVE_LINE_RE.match(line)
            if m:
                flush()
                try:
                    dt = datetime.strptime(f"{m.group('date')} {m.group('time')}", _ARCHIVE_DT_FMT)
                except ValueError:
                    dt = None
                current_lines = [line]
                current_dt = dt
            elif current_lines is not None:
                current_lines.append(line)
            else:
                # A standalone line with no date/time prefix at all and
                # nothing before it to attach to (e.g. a genuine
                # "[UNPARSED - review this line]" entry with no known
                # timestamp) — its own dateless block.
                blocks.append({'datetime': None, 'text': line})
    flush()
    return blocks
