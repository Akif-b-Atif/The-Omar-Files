"""
Computes every statistic shown in the report. All functions take the
enriched DataFrame (from parsing.build_dataframe) and return plain
dicts/lists (JSON-serialisable) so they can feed straight into the HTML,
PDF, and search-JSON builders.
"""
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from parsing import tokenize, EMOJI_RE, WORD_RE, TAG_RE
import chat_config as cfg
from baseline_corpus import BASELINE_MESSAGES


# Matches either a literal two-character "\n" escape sequence (which can
# show up when chat text was round-tripped through something that
# serialized real newlines as a literal backslash + n, e.g. "hi\nthere")
# or an actual newline character. Both are linebreaks for our purposes and
# get collapsed to a single space before word/phrase analysis, so a word
# right after a linebreak doesn't get a stray leading "n" glued onto it
# and isn't accidentally merged with the previous word.
_LINEBREAK_RE = re.compile(r"\\n|\n")


def _clean_for_wordphrase(text):
    """Text cleanup used only for word/phrase/signature frequency analysis
    (not for display or other stats): collapse linebreaks to spaces, and
    strip out "@tag" mentions entirely, since a tag is not a word or part
    of a phrase."""
    t = _LINEBREAK_RE.sub(" ", text)
    t = TAG_RE.sub(" ", t)
    return t


def _iso(ts):
    if pd.isna(ts):
        return None
    return pd.Timestamp(ts).isoformat()


def _build_word_patterns(words):
    escaped = sorted({re.escape(w.lower()) for w in words}, key=len, reverse=True)
    return re.compile(r"\b(?:" + "|".join(escaped) + r")\b", re.I)


def _build_laugh_pattern():
    parts = [re.escape(w.lower()) for w in cfg.LAUGH_WORDS] + list(cfg.LAUGH_REGEX_PATTERNS)
    parts = sorted(set(parts), key=len, reverse=True)
    return re.compile(r"\b(?:" + "|".join(parts) + r")\b", re.I)


SWEAR_PATTERN = _build_word_patterns(cfg.SWEAR_WORDS) if cfg.SWEAR_WORDS else None
LAUGH_PATTERN = _build_laugh_pattern() if (cfg.LAUGH_WORDS or cfg.LAUGH_REGEX_PATTERNS) else None
QSTART_PATTERN = None
if cfg.QUESTION_STARTERS:
    escaped = sorted({re.escape(w.lower()) for w in cfg.QUESTION_STARTERS}, key=len, reverse=True)
    QSTART_PATTERN = re.compile(r"^(?:" + "|".join(escaped) + r")\b", re.I)


# ---------------------------------------------------------------- overall --

def compute_overall(df):
    real = df[df["is_real_text"] | df["is_media"] | df["is_deleted"] | df["is_call"]]
    real = real[~real["is_system"]]

    first_ts, last_ts = df["timestamp"].min(), df["timestamp"].max()
    total_days = (last_ts.date() - first_ts.date()).days + 1

    per_day = real.groupby("date").size()
    busiest_day = per_day.idxmax()
    quietest_day = per_day.idxmin()

    top3_busiest_days = [
        {"date": str(d), "count": int(c)}
        for d, c in per_day.sort_values(ascending=False).head(3).items()
    ]
    top3_quietest_active_days = [
        {"date": str(d), "count": int(c)}
        for d, c in per_day.sort_values(ascending=True).head(3).items()
    ]

    active_days = per_day.index
    all_days = pd.date_range(first_ts.date(), last_ts.date(), freq="D").date
    silent_days = sorted(set(all_days) - set(active_days))

    # every run of consecutive active days, longest first (top 3 kept)
    sorted_days = sorted(active_days)
    streaks = []
    if sorted_days:
        run_start = run_end = sorted_days[0]
        for d in sorted_days[1:]:
            if (d - run_end).days == 1:
                run_end = d
                continue
            streaks.append((run_start, run_end))
            run_start = run_end = d
        streaks.append((run_start, run_end))
    streaks.sort(key=lambda se: -((se[1] - se[0]).days + 1))
    top3_streaks = [
        {"days": (e - s).days + 1, "start": str(s), "end": str(e)}
        for s, e in streaks[:3]
    ]
    best_streak = top3_streaks[0]["days"] if top3_streaks else 0
    best_start = top3_streaks[0]["start"] if top3_streaks else None
    best_end = top3_streaks[0]["end"] if top3_streaks else None

    # longest gaps between consecutive messages (any type incl system), top 3
    ts_sorted = df["timestamp"].sort_values().reset_index(drop=True)
    gaps = ts_sorted.diff().dropna()
    top_gap_idx = gaps.sort_values(ascending=False).head(3).index
    top3_silences = [
        {
            "hours": round(gaps.loc[idx].total_seconds() / 3600, 1),
            "from": _iso(ts_sorted.loc[idx - 1]),
            "to": _iso(ts_sorted.loc[idx]),
        }
        for idx in top_gap_idx
    ]
    longest_gap = gaps.loc[top_gap_idx[0]] if len(top_gap_idx) else pd.Timedelta(0)
    gap_end_ts = ts_sorted.loc[top_gap_idx[0]] if len(top_gap_idx) else None
    gap_start_ts = ts_sorted.loc[top_gap_idx[0] - 1] if len(top_gap_idx) else None

    msg_gaps = real["timestamp"].sort_values().diff().dropna().dt.total_seconds()

    # top 3 longest single messages, by word count, across everyone
    text_real = real[real["is_real_text"]]
    top3_longest_messages = []
    if len(text_real):
        for idx in text_real["word_count"].sort_values(ascending=False).head(3).index:
            row = text_real.loc[idx]
            top3_longest_messages.append({
                "person": row["sender"], "words": int(row["word_count"]),
                "text": row["text"][:300], "date": _iso(row["timestamp"]),
            })

    # top 3 quickest replies: smallest gap between two messages from
    # DIFFERENT senders (a same-sender gap is a double-text, not a reply)
    real_sorted = real.sort_values("timestamp").reset_index(drop=True)
    top3_quickest_replies = []
    if len(real_sorted) > 1:
        gap_secs = real_sorted["timestamp"].diff().dt.total_seconds()
        same_sender = real_sorted["sender"].eq(real_sorted["sender"].shift())
        reply_gaps = gap_secs.where((~same_sender) & (gap_secs > 0))
        for idx in reply_gaps.dropna().sort_values(ascending=True).head(3).index:
            top3_quickest_replies.append({
                "seconds": round(float(reply_gaps.loc[idx]), 1),
                "from": real_sorted.loc[idx - 1, "sender"],
                "to": real_sorted.loc[idx, "sender"],
                "at": _iso(real_sorted.loc[idx, "timestamp"]),
            })

    # top 3 days with the most media shared
    media_per_day = real[real["is_media"]].groupby("date").size()
    top3_media_days = [
        {"date": str(d), "count": int(c)}
        for d, c in media_per_day.sort_values(ascending=False).head(3).items()
    ] if len(media_per_day) else []

    return {
        "total_messages": int(len(real)),
        "total_text_messages": int(real["is_real_text"].sum()),
        "total_media": int(real["is_media"].sum()),
        "total_deleted": int(real["is_deleted"].sum()),
        "total_calls": int(real["is_call"].sum()),
        "total_edited": int(real["is_edited"].sum()),
        "total_system_events": int(df["is_system"].sum()),
        "first_message_ts": _iso(first_ts),
        "last_message_ts": _iso(last_ts),
        "total_days_spanned": int(total_days),
        "active_days": int(len(active_days)),
        "silent_days": int(len(silent_days)),
        "pct_days_active": round(100 * len(active_days) / total_days, 1),
        "avg_messages_per_day": round(len(real) / total_days, 2),
        "avg_messages_per_active_day": round(len(real) / len(active_days), 2),
        "busiest_day": {"date": str(busiest_day), "count": int(per_day.max())},
        "quietest_active_day": {"date": str(quietest_day), "count": int(per_day.min())},
        "longest_active_streak": {
            "days": int(best_streak), "start": best_start, "end": best_end
        },
        "longest_silence": {
            "hours": round(longest_gap.total_seconds() / 3600, 1),
            "from": _iso(gap_start_ts), "to": _iso(gap_end_ts),
        },
        "median_reply_gap_minutes": round(float(np.median(msg_gaps)) / 60, 2) if len(msg_gaps) else None,
        "total_words_sent": int(real["word_count"].sum()),
        "total_characters_sent": int(real["char_count"].sum()),
        "avg_words_per_message": round(float(real.loc[real["is_real_text"], "word_count"].mean()), 2),
        # top-3 "fun facts" categories (see render_funfacts / pdf fun facts)
        "top3_busiest_days": top3_busiest_days,
        "top3_quietest_active_days": top3_quietest_active_days,
        "top3_longest_active_streaks": top3_streaks,
        "top3_longest_silences": top3_silences,
        "top3_longest_messages": top3_longest_messages,
        "top3_quickest_replies": top3_quickest_replies,
        "top3_media_heavy_days": top3_media_days,
    }


# ------------------------------------------------------------- time dist --

def compute_time_distribution(df):
    real = df[(~df["is_system"])]
    by_hour = real.groupby("hour").size().reindex(range(24), fill_value=0)
    weekday_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    by_weekday = real.groupby("weekday").size().reindex(weekday_order, fill_value=0)
    by_month = real.groupby("month_period").size().sort_index()
    per_day = real.groupby("date").size().sort_index()
    heat = real.groupby(["weekday_num", "hour"]).size().unstack(fill_value=0).reindex(range(7), fill_value=0)

    return {
        "by_hour": {int(h): int(c) for h, c in by_hour.items()},
        "by_weekday": {d: int(c) for d, c in by_weekday.items()},
        "by_month": {m: int(c) for m, c in by_month.items()},
        "per_day": {str(d): int(c) for d, c in per_day.items()},
        "heatmap": heat.values.tolist(),  # 7 rows (Mon..Sun) x 24 cols
        "peak_hour": int(by_hour.idxmax()),
        "peak_weekday": str(by_weekday.idxmax()),
        "peak_month": str(by_month.idxmax()) if len(by_month) else None,
    }


# ---------------------------------------------------------- per-person ----

def compute_individual_stats(df, participants, total_days):
    real = df[~df["is_system"]]
    out = {}
    total_msgs_all = len(real)

    # precompute mention data first (needs participants)
    mention_given, mention_received, mention_pairs = _compute_mentions(real, participants)

    # single-pass computation of double-texting & conversation-starts for everyone
    real_sorted_all = real.sort_values("timestamp")
    senders_seq = real_sorted_all["sender"].tolist()
    ts_seq = real_sorted_all["timestamp"].tolist()
    gap_thresh = timedelta(hours=cfg.CONVERSATION_GAP_HOURS)
    double_text_counts = Counter()
    starter_counts = Counter()
    for i in range(1, len(senders_seq)):
        if senders_seq[i] == senders_seq[i - 1]:
            double_text_counts[senders_seq[i - 1]] += 1
        if (ts_seq[i] - ts_seq[i - 1]) >= gap_thresh:
            starter_counts[senders_seq[i]] += 1

    for person in participants:
        mine = real[real["sender"] == person]
        text_mine = mine[mine["is_real_text"]]
        all_text = " ".join(text_mine["text"].tolist())
        # _clean_for_wordphrase strips "@tag" mentions before tokenizing,
        # since a tag isn't vocabulary — otherwise "@Sarah" would inflate
        # someone's vocabulary/word-count stats with everyone else's names.
        tokens = tokenize(_clean_for_wordphrase(all_text))
        vocab = set(tokens)

        n_msgs = len(mine)
        active_days_person = mine["date"].nunique()

        swear_hits = len(SWEAR_PATTERN.findall(all_text)) if SWEAR_PATTERN else 0
        laugh_hits = len(LAUGH_PATTERN.findall(all_text)) if LAUGH_PATTERN else 0

        q_mask = text_mine["text"].str.contains(r"\?") | text_mine["text"].apply(
            lambda t: bool(QSTART_PATTERN.match(t.strip())) if QSTART_PATTERN else False
        )
        n_questions = int(q_mask.sum())

        caps_mask = text_mine["text"].apply(
            lambda t: len(t) >= 4 and t == t.upper() and t != t.lower() and any(c.isalpha() for c in t)
        )
        n_shout = int(caps_mask.sum())

        n_excl = int(text_mine["text"].str.count("!").sum())
        emojis = EMOJI_RE.findall(all_text)
        emoji_counter = Counter()
        for e in emojis:
            for ch in e:
                emoji_counter[ch] += 1
        top_emoji = emoji_counter.most_common(5)

        hour_counts = mine.groupby("hour").size().reindex(range(24), fill_value=0)
        per_day_counts = mine.groupby("date").size().sort_index()

        night_lo, night_hi = cfg.NIGHT_OWL_HOURS
        early_lo, early_hi = cfg.EARLY_BIRD_HOURS
        night_pct = round(100 * hour_counts.loc[night_lo:night_hi - 1].sum() / n_msgs, 1) if n_msgs else 0
        early_pct = round(100 * hour_counts.loc[early_lo:early_hi - 1].sum() / n_msgs, 1) if n_msgs else 0

        longest_msg_row = text_mine.loc[text_mine["word_count"].idxmax()] if len(text_mine) else None

        double_text_rate = round(100 * double_text_counts.get(person, 0) / n_msgs, 1) if n_msgs else 0
        starters = starter_counts.get(person, 0)

        out[person] = {
            "total_messages": int(n_msgs),
            "pct_of_all_messages": round(100 * n_msgs / total_msgs_all, 2) if total_msgs_all else 0,
            "total_text_messages": int(len(text_mine)),
            "media_sent": int(mine["is_media"].sum()),
            "deleted_sent": int(mine["is_deleted"].sum()),
            "edited_sent": int(mine["is_edited"].sum()),
            "active_days": int(active_days_person),
            "avg_messages_per_day_active": round(n_msgs / active_days_person, 2) if active_days_person else 0,
            "avg_messages_per_day_overall": round(n_msgs / total_days, 3) if total_days else 0,
            "total_words": len(tokens),
            "unique_words": len(vocab),
            "vocab_richness_pct": round(100 * len(vocab) / len(tokens), 1) if tokens else 0,
            "avg_words_per_message": round(float(text_mine["word_count"].mean()), 2) if len(text_mine) else 0,
            "avg_chars_per_message": round(float(text_mine["char_count"].mean()), 1) if len(text_mine) else 0,
            "longest_message": {
                "text": longest_msg_row["text"][:300] if longest_msg_row is not None else None,
                "words": int(longest_msg_row["word_count"]) if longest_msg_row is not None else 0,
                "date": _iso(longest_msg_row["timestamp"]) if longest_msg_row is not None else None,
            },
            "swear_count": int(swear_hits),
            "swear_rate_per_100": round(100 * swear_hits / n_msgs, 2) if n_msgs else 0,
            "laugh_count": int(laugh_hits),
            "laugh_rate_per_100": round(100 * laugh_hits / n_msgs, 2) if n_msgs else 0,
            "question_count": n_questions,
            "question_rate_per_100": round(100 * n_questions / n_msgs, 2) if n_msgs else 0,
            "shout_count": n_shout,
            "exclamation_count": n_excl,
            "top_emojis": [{"emoji": e, "count": c} for e, c in top_emoji],
            "total_emojis": int(sum(emoji_counter.values())),
            "hourly_distribution": {int(h): int(c) for h, c in hour_counts.items()},
            "peak_hour": int(hour_counts.idxmax()) if n_msgs else None,
            "night_owl_pct": night_pct,
            "early_bird_pct": early_pct,
            "double_text_rate_pct": double_text_rate,
            "conversation_starts": starters,
            "mentions_given": mention_given.get(person, 0),
            "mentions_received": mention_received.get(person, 0),
            "first_message": _iso(mine["timestamp"].min()) if n_msgs else None,
            "last_message": _iso(mine["timestamp"].max()) if n_msgs else None,
            "messages_per_day_timeline": {str(d): int(c) for d, c in per_day_counts.items()},
        }

    return out, mention_pairs


def _compile_mention_patterns(participants):
    variants = []  # (pattern_str, canonical_name)
    for p in participants:
        variants.append((p, p))
        first = p.split()[0]
        if first != p:
            variants.append((first, p))
    variants = sorted(set(variants), key=lambda x: -len(x[0]))
    alt = "|".join(re.escape(v) for v, _ in variants)
    pattern = re.compile(r"@(" + alt + r")\b", re.I)
    lookup = {}
    for v, canon in variants:
        lookup[v.lower()] = canon
    return pattern, lookup


def _compute_mentions(real, participants):
    pattern, lookup = _compile_mention_patterns(participants)
    given = Counter()
    received = Counter()
    pairs = Counter()

    for sender, text in zip(real["sender"], real["text"]):
        for m in pattern.finditer(text):
            canon = lookup.get(m.group(1).lower())
            if canon is None:
                continue
            given[sender] += 1
            received[canon] += 1
            pairs[(sender, canon)] += 1

    pair_list = [
        {"from": a, "to": b, "count": c}
        for (a, b), c in sorted(pairs.items(), key=lambda x: -x[1])
    ]
    return given, received, pair_list


# --------------------------------------------------------- words/phrases --

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WS_RE = re.compile(r"\s+")

_baseline_cache = None


def _baseline_word_freq():
    """Tokenizes baseline_corpus.BASELINE_MESSAGES (a synthetic, generic
    group chat -- see that file) exactly once and caches the result: a
    Counter of word -> count, plus the total token count. Used as the
    "what does a normal chat sound like" reference for compute_word_stats'
    comparative "most repeated words" ranking. Not filtered by
    MIN_WORD_LENGTH/EXTRA_STOPWORDS here -- callers look words up in this
    counter by exact text, so it needs every word available regardless of
    length; the filtering happens on the target side instead."""
    global _baseline_cache
    if _baseline_cache is None:
        counter = Counter()
        for msg in BASELINE_MESSAGES:
            counter.update(tokenize(_clean_for_wordphrase(msg)))
        _baseline_cache = (counter, sum(counter.values()))
    return _baseline_cache


def _comparative_rank(target_counter, target_total, baseline_counter, baseline_total,
                       eligible_words, top_n, smoothing=1.0):
    """Ranks `eligible_words` by how much MORE OFTEN they occur in the
    target text than in the baseline text (rate in target / rate in
    baseline), instead of by raw count. This is what turns "most repeated"
    into "most distinctive/signature" -- a word said constantly in BOTH
    the target and the baseline (generic chat filler) scores low, while a
    word said constantly in the target but rarely/never in the baseline
    (this group's actual topics, names, running jokes) scores high.
    Laplace/add-one smoothing on the baseline side keeps a word that's
    simply absent from the baseline from getting an undefined/infinite
    score, and keeps baseline rarities from swinging wildly.
    Returns a list of (word, target_count, score) tuples, highest score
    first, truncated to top_n."""
    baseline_vocab = len(baseline_counter) or 1
    scored = []
    for w in eligible_words:
        c = target_counter[w]
        target_rate = c / target_total if target_total else 0
        baseline_rate = (baseline_counter.get(w, 0) + smoothing) / (baseline_total + smoothing * baseline_vocab)
        score = target_rate / baseline_rate if baseline_rate else 0
        scored.append((w, c, score))
    scored.sort(key=lambda x: (-x[2], -x[1]))
    return scored[:top_n]


def _build_word_index(df, cfg, apply_stopwords=True):
    """Tokenizes every real text message in `df` (tags/@mentions and
    linebreaks stripped first — see _clean_for_wordphrase) and returns a
    dict of counters/lookups shared by compute_word_stats and
    compute_arc_signature_stats, so both build their word frequencies the
    same way instead of duplicating this loop."""
    real = df[(~df["is_system"]) & df["is_real_text"]]
    global_counter = Counter()
    per_person_counter = defaultdict(Counter)
    first_seen, last_seen = {}, {}
    first_seen_by, last_seen_by = {}, {}

    for sender, text, ts in zip(real["sender"], real["text"], real["timestamp"]):
        toks = [t for t in tokenize(_clean_for_wordphrase(text)) if len(t) >= cfg.MIN_WORD_LENGTH]
        if apply_stopwords:
            toks = [t for t in toks if t not in cfg.EXTRA_STOPWORDS]
        for t in toks:
            global_counter[t] += 1
            per_person_counter[sender][t] += 1
            if t not in first_seen or ts < first_seen[t]:
                first_seen[t] = ts
                first_seen_by[t] = sender
            if t not in last_seen or ts > last_seen[t]:
                last_seen[t] = ts
                last_seen_by[t] = sender

    return {
        "counter": global_counter, "per_person": per_person_counter,
        "first_seen": first_seen, "last_seen": last_seen,
        "first_seen_by": first_seen_by, "last_seen_by": last_seen_by,
    }


def _build_phrase_index(df, cfg):
    """Same idea as _build_word_index, but for whole-message "phrases"
    (see _normalize_message) — shared by compute_phrase_stats and
    compute_arc_signature_stats."""
    real = df[(~df["is_system"]) & df["is_real_text"]]
    global_counter = Counter()
    per_person_counter = defaultdict(Counter)
    first_seen, last_seen = {}, {}
    first_seen_by, last_seen_by = {}, {}
    display_text = {}

    for sender, text, ts in zip(real["sender"], real["text"], real["timestamp"]):
        norm = _normalize_message(_clean_for_wordphrase(text))
        if len(norm) < cfg.MIN_PHRASE_LENGTH:
            continue
        global_counter[norm] += 1
        per_person_counter[sender][norm] += 1
        if norm not in first_seen or ts < first_seen[norm]:
            first_seen[norm] = ts
            first_seen_by[norm] = sender
        if norm not in last_seen or ts > last_seen[norm]:
            last_seen[norm] = ts
            last_seen_by[norm] = sender
        if norm not in display_text:
            display_text[norm] = _WS_RE.sub(" ", _clean_for_wordphrase(text)).strip()[:200]

    return {
        "counter": global_counter, "per_person": per_person_counter,
        "first_seen": first_seen, "last_seen": last_seen,
        "first_seen_by": first_seen_by, "last_seen_by": last_seen_by,
        "display": display_text,
    }


def _normalize_message(text):
    """Collapse a message down to the form used to decide whether two
    messages are "the same phrase": strip emojis, strip punctuation,
    lowercase, and collapse whitespace/newlines. Two messages that are
    identical except for emojis/punctuation/casing normalize to the same
    string."""
    t = EMOJI_RE.sub("", text)
    t = t.lower()
    t = _PUNCT_RE.sub(" ", t)
    t = _WS_RE.sub(" ", t).strip()
    return t


def _group_signature_by_person(signature_all, participants, individual_stats,
                                top_n=None, min_messages=None):
    """Takes a flat list of signature entries (each with a 'person' key) and
    groups them into {person: [top_n entries]} for every participant who
    has at least `min_messages` total messages, ordered by dominance then
    raw count within each person. Only participants who end up with at
    least one qualifying entry are included, and the dict preserves the
    `participants` ordering (i.e. most-active person first)."""
    top_n = top_n or cfg.SIGNATURE_TOP_N_PER_PERSON
    min_messages = cfg.SIGNATURE_MIN_MESSAGES if min_messages is None else min_messages

    grouped = defaultdict(list)
    for item in signature_all:
        grouped[item["person"]].append(item)

    result = {}
    for p in participants:
        if individual_stats is not None:
            if individual_stats.get(p, {}).get("total_messages", 0) < min_messages:
                continue
        items = sorted(grouped.get(p, []), key=lambda x: (-x["dominance_pct"], -x["person_count"]))[:top_n]
        if items:
            result[p] = items
    return result


def compute_word_stats(df, participants, individual_stats=None, cfg=cfg):
    """cfg: optional override namespace (see chat_config.make_profile) so
    this can be re-run with looser noise thresholds — e.g. for a "last N
    days" snapshot, which has far fewer messages than the full archive."""
    idx = _build_word_index(df, cfg, apply_stopwords=True)
    global_counter, per_person_counter = idx["counter"], idx["per_person"]
    first_seen, last_seen = idx["first_seen"], idx["last_seen"]
    first_seen_by, last_seen_by = idx["first_seen_by"], idx["last_seen_by"]

    eligible = {w: c for w, c in global_counter.items() if c >= cfg.MIN_REPEAT_COUNT}

    # "Most repeated words" used to just be `eligible` sorted by raw count.
    # But once pronouns/verbs/prepositions/names are filtered out via
    # EXTRA_STOPWORDS, what's left over skews heavily towards words every
    # group chat repeats constantly ("literally", "dinner", "weekend"),
    # not anything specific to THIS chat. Instead, rank by how much MORE
    # this chat says each word than a synthetic, completely generic
    # baseline group chat does (baseline_corpus.py) — that surfaces this
    # chat's actual topical/signature vocabulary instead of universal
    # filler.
    baseline_counter, baseline_total = _baseline_word_freq()
    target_total = sum(global_counter.values())
    ranked = _comparative_rank(global_counter, target_total, baseline_counter,
                                baseline_total, eligible.keys(), cfg.TOP_N)

    top_words = []
    for w, c, score in ranked:
        top_sender = max(participants, key=lambda p: per_person_counter[p].get(w, 0))
        top_words.append({
            "word": w, "count": c, "vs_baseline": round(score, 1),
            "top_sayer": top_sender, "top_sayer_count": per_person_counter[top_sender].get(w, 0),
            "first_instance": {"by": first_seen_by[w], "at": _iso(first_seen[w])},
            "last_instance": {"by": last_seen_by[w], "at": _iso(last_seen[w])},
        })

    # signature words: for every word, whoever says it most "owns" it.
    # Grouped per person below instead of one global top-N list, so every
    # active member (>= SIGNATURE_MIN_MESSAGES messages) gets their own
    # top-SIGNATURE_TOP_N_PER_PERSON signature words.
    signature_words_all = []
    for w, c in eligible.items():
        best_person, best_count = None, 0
        for p in participants:
            pc = per_person_counter[p].get(w, 0)
            if pc > best_count:
                best_person, best_count = p, pc
        if best_count >= cfg.MIN_REPEAT_COUNT:
            dominance = best_count / c
            signature_words_all.append({
                "word": w, "person": best_person, "person_count": best_count,
                "total_count": c, "dominance_pct": round(100 * dominance, 1),
                "first_instance": {"by": first_seen_by[w], "at": _iso(first_seen[w])},
                "last_instance": {"by": last_seen_by[w], "at": _iso(last_seen[w])},
            })
    signature_words = _group_signature_by_person(
        signature_words_all, participants, individual_stats,
        top_n=cfg.SIGNATURE_TOP_N_PER_PERSON, min_messages=cfg.SIGNATURE_MIN_MESSAGES)

    return {
        "top_words": top_words,
        "signature_words": signature_words,
        "vocab_overall": len(global_counter),
    }


def compute_phrase_stats(df, participants, individual_stats=None, cfg=cfg):
    """A "phrase" here means a whole message, not an n-gram fragment. Two
    messages are treated as the SAME phrase if they're identical once you
    ignore emojis, punctuation, and capitalization (see _normalize_message).
    This avoids the old n-gram approach's failure mode where one long
    message ("meow meow meow meow...") would get sliced into dozens of
    overlapping fake "repeats" of the same short fragment.

    cfg: optional override namespace (see chat_config.make_profile), same
    idea as compute_word_stats."""
    idx = _build_phrase_index(df, cfg)
    global_counter, per_person_counter = idx["counter"], idx["per_person"]
    first_seen, last_seen = idx["first_seen"], idx["last_seen"]
    first_seen_by, last_seen_by = idx["first_seen_by"], idx["last_seen_by"]
    display_text = idx["display"]  # normalized phrase -> a representative original message, for display

    eligible = {p: c for p, c in global_counter.items() if c >= cfg.MIN_REPEAT_COUNT}

    # top phrases: rank by how many times that exact message was sent
    ranked = sorted(eligible.keys(), key=lambda p: (-eligible[p], -len(p)))[: cfg.TOP_N]
    top_phrases = []
    for ph in ranked:
        c = eligible[ph]
        top_sender = max(participants, key=lambda p: per_person_counter[p].get(ph, 0))
        top_phrases.append({
            "phrase": display_text.get(ph, ph), "count": c,
            "top_sayer": top_sender, "top_sayer_count": per_person_counter[top_sender].get(ph, 0),
            "first_instance": {"by": first_seen_by[ph], "at": _iso(first_seen[ph])},
            "last_instance": {"by": last_seen_by[ph], "at": _iso(last_seen[ph])},
        })

    # signature phrases: same per-person grouping as signature words
    signature_phrases_all = []
    for ph, c in eligible.items():
        best_person, best_count = None, 0
        for p in participants:
            pc = per_person_counter[p].get(ph, 0)
            if pc > best_count:
                best_person, best_count = p, pc
        if best_count >= cfg.MIN_REPEAT_COUNT:
            dominance = best_count / c
            signature_phrases_all.append({
                "phrase": display_text.get(ph, ph), "person": best_person, "person_count": best_count,
                "total_count": c, "dominance_pct": round(100 * dominance, 1),
                "first_instance": {"by": first_seen_by[ph], "at": _iso(first_seen[ph])},
                "last_instance": {"by": last_seen_by[ph], "at": _iso(last_seen[ph])},
            })
    signature_phrases = _group_signature_by_person(
        signature_phrases_all, participants, individual_stats,
        top_n=cfg.SIGNATURE_TOP_N_PER_PERSON, min_messages=cfg.SIGNATURE_MIN_MESSAGES)

    return {"top_phrases": top_phrases, "signature_phrases": signature_phrases}


def compute_arc_signature_stats(df_arc, df_archive, participants, cfg=cfg):
    """Signature words/phrases for ONE arc/mini-arc.

    This intentionally does NOT reuse compute_word_stats'/compute_phrase_
    stats' per-person "signature" grouping — a per-person breakdown inside
    a single arc mostly just re-surfaces whatever that person's usual
    words are everywhere else too, which is redundant with the main
    report's own per-person signature words section.

    Instead, this compares the arc's own word/phrase frequencies against
    the frequencies across the ENTIRE archive (`df_archive`, i.e. the same
    dataframe compute_bundle ran the main report on), the same
    "comparative rate" idea compute_word_stats uses against the synthetic
    baseline — except here the "baseline" is this chat's own overall
    normal behaviour, not a generic outside chat. What comes out the other
    end is this arc's own topic fingerprint: whatever it talked about
    noticeably more than the chat does normally, i.e. what actually makes
    this slice of time distinct from the rest of the archive.

    Returns {"signature_words": [...], "signature_phrases": [...]}, each a
    flat list (NOT grouped by person) ranked by that comparative score."""
    word_idx_arc = _build_word_index(df_arc, cfg, apply_stopwords=True)
    word_idx_archive = _build_word_index(df_archive, cfg, apply_stopwords=True)
    arc_counter, per_person = word_idx_arc["counter"], word_idx_arc["per_person"]
    archive_counter = word_idx_archive["counter"]
    arc_total = sum(arc_counter.values())
    archive_total = sum(archive_counter.values())

    eligible = {w: c for w, c in arc_counter.items() if c >= cfg.MIN_REPEAT_COUNT}
    ranked = _comparative_rank(arc_counter, arc_total, archive_counter,
                                archive_total, eligible.keys(), cfg.TOP_N)

    signature_words = []
    for w, c, score in ranked:
        top_sender = max(participants, key=lambda p: per_person[p].get(w, 0)) if participants else None
        signature_words.append({
            "word": w, "count_in_arc": c, "count_in_archive": archive_counter.get(w, 0),
            "vs_archive": round(score, 1),
            "top_sayer": top_sender,
            "top_sayer_count": per_person[top_sender].get(w, 0) if top_sender else 0,
            "first_instance": {"by": word_idx_arc["first_seen_by"][w], "at": _iso(word_idx_arc["first_seen"][w])},
            "last_instance": {"by": word_idx_arc["last_seen_by"][w], "at": _iso(word_idx_arc["last_seen"][w])},
        })

    phrase_idx_arc = _build_phrase_index(df_arc, cfg)
    phrase_idx_archive = _build_phrase_index(df_archive, cfg)
    arc_pcounter, per_person_p = phrase_idx_arc["counter"], phrase_idx_arc["per_person"]
    archive_pcounter = phrase_idx_archive["counter"]
    arc_ptotal = sum(arc_pcounter.values())
    archive_ptotal = sum(archive_pcounter.values())

    eligible_p = {p: c for p, c in arc_pcounter.items() if c >= cfg.MIN_REPEAT_COUNT}
    ranked_p = _comparative_rank(arc_pcounter, arc_ptotal, archive_pcounter,
                                  archive_ptotal, eligible_p.keys(), cfg.TOP_N)

    signature_phrases = []
    for ph, c, score in ranked_p:
        top_sender = max(participants, key=lambda p: per_person_p[p].get(ph, 0)) if participants else None
        signature_phrases.append({
            "phrase": phrase_idx_arc["display"].get(ph, ph),
            "count_in_arc": c, "count_in_archive": archive_pcounter.get(ph, 0),
            "vs_archive": round(score, 1),
            "top_sayer": top_sender,
            "top_sayer_count": per_person_p[top_sender].get(ph, 0) if top_sender else 0,
            "first_instance": {"by": phrase_idx_arc["first_seen_by"][ph], "at": _iso(phrase_idx_arc["first_seen"][ph])},
            "last_instance": {"by": phrase_idx_arc["last_seen_by"][ph], "at": _iso(phrase_idx_arc["last_seen"][ph])},
        })

    return {"signature_words": signature_words, "signature_phrases": signature_phrases}


def compute_leaderboards(individual_stats):
    """Simple sorted leaderboards for quick 'who does X most' tables."""
    def rank(key, reverse=True):
        return sorted(
            [{"person": p, "value": v[key]} for p, v in individual_stats.items()],
            key=lambda x: x["value"], reverse=reverse,
        )

    return {
        "most_messages": rank("total_messages"),
        "biggest_vocab": rank("unique_words"),
        "most_swears": rank("swear_count"),
        "most_swears_rate": rank("swear_rate_per_100"),
        "most_laughs": rank("laugh_count"),
        "most_laughs_rate": rank("laugh_rate_per_100"),
        "most_questions": rank("question_count"),
        "most_mentions_given": rank("mentions_given"),
        "most_mentions_received": rank("mentions_received"),
        "most_night_owl": rank("night_owl_pct"),
        "most_early_bird": rank("early_bird_pct"),
        "most_double_texting": rank("double_text_rate_pct"),
        "most_conversation_starts": rank("conversation_starts"),
        "longest_avg_messages": rank("avg_words_per_message"),
        "most_shouting": rank("shout_count"),
        "most_exclamations": rank("exclamation_count"),
        "most_emojis": rank("total_emojis"),
        "most_media": rank("media_sent"),
        "most_deleted": rank("deleted_sent"),
        "most_edited": rank("edited_sent"),
    }
