"""
Chain detection: finds the longest "chains" in a chat, i.e. a message (or a
cycle of messages) that repeats back to back, e.g.

    Hi / Hi / Hi                    -> cycle of 1, repeated 3x
    Hi / Hey / Hi / Hey / Hi / Hey  -> cycle of 2, repeated 3x

Matching ignores case and punctuation and tolerates a 1-character typo (one
substitution, insertion, deletion, or swapped adjacent letters).

A single unrelated message in the middle of a chain does NOT break it
(tolerance = 1); two unrelated messages in a row do.

Ported from the standalone find_chains.py. The detection logic is the same;
what changed is the plumbing: it works on the analyzer's dataframe instead of
re-parsing the file, every tunable is an explicit argument / chat_config
constant instead of a module global, and the result is plain JSON-friendly
dicts that the HTML/PDF reports render.
"""
import re
import unicodedata

# Things WhatsApp writes in place of real text, checked on the NORMALIZED
# text (lowercase, no punctuation), so "<Media omitted>" -> "media omitted".
# Backstop for anything the parser's own is_real_text flag lets through.
PLACEHOLDER_RE = re.compile(
    r"^(media|image|video|audio|sticker|gif|document|contact card|video note|voice message) omitted$"
    r"|^this message was deleted$|^you deleted this message$"
    r"|^missed (voice|video) call$|^null$|^attached .*$|^waiting for this message.*$"
)


def normalize(text):
    """Lowercase, strip punctuation/symbols, collapse whitespace (emojis are kept)."""
    text = unicodedata.normalize("NFKC", text).casefold()
    # drop punctuation (P*) and plain symbols like < > + = ~ $ (Sm/Sc/Sk); keep emojis (So)
    text = "".join(ch for ch in text
                   if not (unicodedata.category(ch).startswith("P")
                           or unicodedata.category(ch) in ("Sm", "Sc", "Sk")))
    return " ".join(text.split())


def similar(a, b, min_fuzzy_len=4):
    """True if a and b are equal or differ by one typo. The typo tolerance
    only applies when both are at least `min_fuzzy_len` long, so 'hi' doesn't
    match 'ho'."""
    if not a or not b:
        return False
    if a == b:
        return True
    la, lb = len(a), len(b)
    if min(la, lb) < min_fuzzy_len or abs(la - lb) > 1:
        return False

    if la == lb:
        first = -1
        for i in range(la):
            if a[i] != b[i]:
                if first == -1:
                    first = i
                else:
                    # second mismatch: only OK if it's an adjacent swap and nothing else differs
                    return (i == first + 1 and a[first] == b[i] and a[i] == b[first]
                            and a[i + 1:] == b[i + 1:])
        return True  # exactly one substitution

    # lengths differ by 1: one insertion/deletion
    if la > lb:
        a, b = b, a
    for i in range(len(a)):
        if a[i] != b[i]:
            return a[i:] == b[i + 1:]
    return True


def is_primitive(cycle, min_fuzzy_len=4):
    """False if the cycle is just a shorter cycle repeated, e.g. [A, A] or [A, B, A, B]."""
    p = len(cycle)
    for q in range(1, p):
        if p % q == 0 and all(similar(cycle[i], cycle[i + q], min_fuzzy_len)
                              for i in range(p - q)):
            return False
    return True


def _extend(norm, cycle, pos, phase, direction, tolerance, min_fuzzy_len):
    """Walks away from `pos` (forward: direction=+1, backward: -1), accepting
    the next message that matches the next slot of the pattern `cycle`. Up to
    `tolerance` unrelated messages may sit between two chain messages; more
    than that ends the walk. Every message is compared to the ORIGINAL
    pattern (not its neighbour), so fuzzy matches can't drift. Returns the
    accepted indices in the order they were found."""
    p, n = len(cycle), len(norm)
    found = []
    while True:
        expected, hit = cycle[phase % p], None
        for step in range(1, tolerance + 2):
            j = pos + direction * step
            if not 0 <= j < n:
                break
            if similar(expected, norm[j], min_fuzzy_len):
                hit = j
                break
        if hit is None:
            return found
        found.append(hit)
        pos, phase = hit, phase + direction


def find_chains(norm, senders, max_cycle=8, min_length=3, min_participants=2,
                allow_solo_cycles=True, tolerance=1, min_fuzzy_len=4):
    """Returns non-overlapping chains as (n_members, cycle_length,
    member_indices) tuples, longest first (ties: smaller cycle, then earliest).

    For each cycle length p: take p consecutive messages as the pattern, then
    keep walking forward (and backward, which catches a chain whose first
    cycle had an interruption in it). A chain needs at least two full cycles
    and `min_length` members. One person alone only counts if they repeat a
    multi-message cycle (p > 1) and `allow_solo_cycles` is set; one person
    repeating a single message is just spam. Empty entries never match and so
    count as interruptions.
    """
    n = len(norm)
    candidates = []

    for p in range(1, max_cycle + 1):
        i = 0
        while i < n - p:
            first = norm[i]
            if not first:
                i += 1
                continue
            # quick reject: the pattern must start again within tolerance of the first cycle's end
            if not any(similar(first, norm[j], min_fuzzy_len)
                       for j in range(i + p, min(n, i + p + tolerance + 1))):
                i += 1
                continue
            cycle = norm[i:i + p]
            if not all(cycle):
                i += 1
                continue

            members = list(range(i, i + p))
            members += _extend(norm, cycle, members[-1], p, +1, tolerance, min_fuzzy_len)

            if len(members) < 2 * p:        # fewer than two full cycles
                i += 1
                continue

            back = _extend(norm, cycle, members[0], p - 1, -1, tolerance, min_fuzzy_len)
            members = back[::-1] + members

            i = members[-1] + 1             # resume after this chain

            if len(members) < min_length or not is_primitive(cycle, min_fuzzy_len):
                continue
            people = len({senders[m] for m in members})
            solo_ok = allow_solo_cycles and people == 1 and p > 1
            if people >= min_participants or solo_ok:
                candidates.append((len(members), p, members))

    candidates.sort(key=lambda c: (-c[0], c[1], c[2][0]))

    # Keep only non-overlapping chains
    used = bytearray(n)
    chosen = []
    for count, p, members in candidates:
        a, b = members[0], members[-1] + 1
        if used.find(1, a, b) == -1:
            used[a:b] = b"\x01" * (b - a)
            chosen.append((count, p, members))
    return chosen


def format_duration(seconds):
    """1h 5m / 4m 12s / 30s -- two most significant units, for report text."""
    seconds = int(seconds)
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def compute_chain_stats(df, cfg):
    """Chain section data for `df` (the analyzer's message dataframe).

    System rows are dropped from the sequence (they neither break a chain nor
    count as an interruption, same as the standalone script); placeholders
    (media/deleted/calls) stay in it as empty entries, which match nothing, so
    they count as interruptions: one is tolerated, CHAIN_TOLERANCE+1 in a row
    end the chain.

    Returns {"chains": [...top CHAIN_TOP_N...], "total_found": int}. Each
    chain is JSON-friendly:
      length (members, i.e. NOT counting interruptions), cycle_length,
      repetitions, start/end (ISO), duration_seconds,
      participants [{"name", "count"}] (members only),
      interruptions {"count", "by": [{"name", "count"}]},
      pattern [{"sender", "text"}] (the first cycle),
      messages [{"at", "sender", "text", "interruption"}] (everything from the
      first to the last member, capped at CHAIN_MAX_SHOWN_MESSAGES),
      span (messages from first to last member) and messages_truncated.
    """
    rows = df[~df["is_system"]]
    senders = rows["sender"].tolist()
    stamps = rows["timestamp"].tolist()
    raw_texts = rows["text"].tolist()
    real = rows["is_real_text"].tolist()

    norm = []
    for text, is_real in zip(raw_texts, real):
        t = normalize(text) if is_real else ""
        norm.append("" if PLACEHOLDER_RE.match(t) else t)

    found = find_chains(
        norm, senders, max_cycle=cfg.CHAIN_MAX_CYCLE, min_length=cfg.CHAIN_MIN_LENGTH,
        min_participants=cfg.CHAIN_MIN_PARTICIPANTS,
        allow_solo_cycles=cfg.CHAIN_ALLOW_SOLO_CYCLES, tolerance=cfg.CHAIN_TOLERANCE,
        min_fuzzy_len=cfg.CHAIN_MIN_FUZZY_LEN,
    )

    def tally(names):
        counts = {}
        for name in names:
            counts[name] = counts.get(name, 0) + 1
        return [{"name": k, "count": v} for k, v in sorted(counts.items(), key=lambda kv: -kv[1])]

    chains = []
    for count, p, members in found[:cfg.CHAIN_TOP_N]:
        first, last = members[0], members[-1]
        member_set = set(members)
        span = last - first + 1
        interrupting = [i for i in range(first, last + 1) if i not in member_set]
        shown = min(span, cfg.CHAIN_MAX_SHOWN_MESSAGES)
        chains.append({
            "length": count, "cycle_length": p, "repetitions": round(count / p, 2),
            "start": stamps[first].isoformat(), "end": stamps[last].isoformat(),
            "duration_seconds": int((stamps[last] - stamps[first]).total_seconds()),
            "participants": tally(senders[m] for m in members),
            "interruptions": {"count": len(interrupting),
                              "by": tally(senders[i] for i in interrupting)},
            "pattern": [{"sender": senders[m], "text": raw_texts[m]} for m in members[:p]],
            "messages": [
                {"at": stamps[i].isoformat(), "sender": senders[i], "text": raw_texts[i],
                 "interruption": i not in member_set}
                for i in range(first, first + shown)
            ],
            "span": span, "messages_truncated": shown < span,
        })
    return {"chains": chains, "total_found": len(found)}
