"""
Parsing layer: turns the raw WhatsApp-style .txt export into a clean
pandas DataFrame, one row per message (system messages included, flagged).
"""
import re
import pandas as pd
import numpy as np

# --- regexes -----------------------------------------------------------

# Leading invisible marks WhatsApp sometimes inserts (LRM/RLM/BOM)
_INVISIBLE = "\u200e\u200f\ufeff"

DATE_PREFIX_RE = re.compile(
    r"^[" + _INVISIBLE + r"]*(\d{1,2}-[A-Za-z]{3}-\d{4}), (\d{1,2}:\d{2}(?::\d{2})?) - "
)
MSG_RE = re.compile(
    r"^[" + _INVISIBLE + r"]*(\d{1,2}-[A-Za-z]{3}-\d{4}), (\d{1,2}:\d{2}(?::\d{2})?) - "
    r"([^:\n]{1,40}?): (.*)$"
)

EDITED_SUFFIX_RE = re.compile(r"\s*<This message was edited>\s*$", re.I)
MEDIA_RE = re.compile(
    r"^[" + _INVISIBLE + r"]*(<Media omitted>|image omitted|video omitted|"
    r"GIF omitted|sticker omitted|audio omitted|Contact card omitted|"
    r"document omitted)\s*$",
    re.I,
)
DELETED_RE = re.compile(r"(?:this message was deleted|you deleted this message)", re.I)
CALL_RE = re.compile(r"(?:missed voice call|missed video call|^voice call$|^video call$)", re.I)

WORD_RE = re.compile(r"[A-Za-z']+")
# A "@name" tag/mention token (e.g. "@Sarah") - used to exclude tags from
# word/phrase frequency analysis, since a tag isn't vocabulary.
TAG_RE = re.compile(r"@\w+", re.UNICODE)
EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0001F1E6-\U0001F1FF"
    "\U00002190-\U000021FF"
    "\U00002B00-\U00002BFF"
    "]+",
    flags=re.UNICODE,
)


def parse_chat_file(filepath, encoding="utf-8"):
    """Parse a WhatsApp-style export .txt into a list of raw message dicts."""
    records = []
    cur = None

    with open(filepath, "r", encoding=encoding, errors="replace") as f:
        for raw_line in f:
            line = raw_line.rstrip("\n").rstrip("\r")
            if not line:
                # blank line: treat as continuation (preserves paragraph breaks)
                if cur is not None:
                    cur["text"] += "\n"
                continue

            m = MSG_RE.match(line)
            if m:
                if cur is not None:
                    records.append(cur)
                date_s, time_s, sender, text = m.groups()
                cur = {
                    "date_s": date_s,
                    "time_s": time_s,
                    "sender": sender.strip(),
                    "text": text,
                    "is_system": False,
                }
                continue

            dm = DATE_PREFIX_RE.match(line)
            if dm:
                if cur is not None:
                    records.append(cur)
                date_s, time_s = dm.groups()
                remainder = line[dm.end():]
                cur = {
                    "date_s": date_s,
                    "time_s": time_s,
                    "sender": None,
                    "text": remainder,
                    "is_system": True,
                }
                continue

            # continuation of previous (multi-line) message
            if cur is not None:
                cur["text"] += "\n" + line
            # else: junk line before any timestamped line seen -> dropped

    if cur is not None:
        records.append(cur)

    return records


def build_dataframe(records):
    df = pd.DataFrame.from_records(records)
    if df.empty:
        raise ValueError(
            "No messages were parsed. Check that Full_Archive.txt matches the "
            "expected 'DD-Mon-YYYY, HH:MM - Sender: Message' format."
        )

    df["timestamp"] = pd.to_datetime(
        df["date_s"] + " " + df["time_s"], format="%d-%b-%Y %H:%M", errors="coerce"
    )
    n_bad = df["timestamp"].isna().sum()
    if n_bad:
        # fallback: let pandas guess (handles 12h AM/PM variants etc.)
        mask = df["timestamp"].isna()
        df.loc[mask, "timestamp"] = pd.to_datetime(
            df.loc[mask, "date_s"] + " " + df.loc[mask, "time_s"], errors="coerce"
        )
    df = df.dropna(subset=["timestamp"]).reset_index(drop=True)

    df["text"] = df["text"].fillna("")
    df["is_edited"] = df["text"].str.contains(EDITED_SUFFIX_RE)
    df["text"] = df["text"].apply(lambda t: EDITED_SUFFIX_RE.sub("", t))

    stripped = df["text"].str.strip()
    df["is_media"] = stripped.str.match(MEDIA_RE)
    df["is_deleted"] = stripped.str.contains(DELETED_RE)
    df["is_call"] = stripped.str.contains(CALL_RE)
    df["is_system"] = df["is_system"].fillna(False)

    df["is_real_text"] = (
        (~df["is_system"]) & (~df["is_media"]) & (~df["is_deleted"]) & (~df["is_call"])
        & (df["text"].str.strip().str.len() > 0)
    )

    df["date"] = df["timestamp"].dt.date
    df["hour"] = df["timestamp"].dt.hour
    df["weekday"] = df["timestamp"].dt.day_name()
    df["weekday_num"] = df["timestamp"].dt.weekday
    df["month_period"] = df["timestamp"].dt.to_period("M").astype(str)
    df["char_count"] = df["text"].str.len()
    df["word_count"] = df["text"].apply(lambda t: len(WORD_RE.findall(t)))

    df = df.sort_values("timestamp").reset_index(drop=True)
    return df


def get_participants(df, min_messages=1):
    """Return list of real senders (excludes system rows), sorted by message count desc."""
    counts = df.loc[~df["is_system"], "sender"].value_counts()
    counts = counts[counts >= min_messages]
    return list(counts.index)


def tokenize(text):
    return [w.strip("'").lower() for w in WORD_RE.findall(text) if w.strip("'")]
