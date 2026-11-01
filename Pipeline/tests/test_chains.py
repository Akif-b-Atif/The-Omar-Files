"""
test_chains.py -- chain detection (Tools/chat_analyzer/chains.py): matching,
cycle detection, interruption tolerance, the participant rules, and the
dataframe wrapper.
"""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "Tools" / "chat_analyzer"))

import chat_config as cfg  # noqa: E402
from chains import (  # noqa: E402
    compute_chain_stats, find_chains, format_duration, is_primitive, normalize, similar,
)
from parsing import build_dataframe  # noqa: E402


def _df(messages):
    """messages: list of (sender, text); one per minute."""
    return build_dataframe([
        {"date_s": "01-Aug-2026", "time_s": f"{i // 60:02d}:{i % 60:02d}",
         "sender": sender, "text": text, "is_system": False}
        for i, (sender, text) in enumerate(messages)
    ])


def test_normalize_ignores_case_and_punctuation_but_keeps_emoji():
    assert normalize("  Hello,   WORLD!! 😂") == "hello world 😂"


def test_similar_tolerates_exactly_one_typo():
    assert similar("hello", "hello")
    assert similar("hello", "hallo")            # substitution
    assert similar("hello", "helo")             # deletion
    assert similar("hello", "helllo")           # insertion
    assert similar("hello", "hlelo")            # adjacent swap
    assert not similar("hello", "hxllx")        # two typos
    assert not similar("hello", "hlxlo")


def test_short_messages_get_no_typo_tolerance():
    assert not similar("hi", "ho")
    assert similar("hi", "hi")
    assert not similar("", "")
    assert similar("hey", "hay", min_fuzzy_len=3)


def test_is_primitive():
    assert is_primitive(["a", "b"])
    assert not is_primitive(["hello", "hello"])
    assert not is_primitive(["hello", "world", "hello", "world"])


def test_single_message_chain_between_people():
    norm = ["x", "hi", "hi", "hi", "hi", "y"]
    senders = ["A", "A", "B", "A", "B", "A"]
    assert find_chains(norm, senders) == [(4, 1, [1, 2, 3, 4])]


def test_one_person_repeating_one_message_is_spam_not_a_chain():
    assert find_chains(["hi"] * 5, ["A"] * 5) == []
    assert find_chains(["hi"] * 5, ["A"] * 5, min_participants=1) == [(5, 1, [0, 1, 2, 3, 4])]


def test_one_person_repeating_a_two_message_cycle_counts_unless_disabled():
    norm = ["hi", "hey", "hi", "hey", "hi", "hey"]
    assert find_chains(norm, ["A"] * 6) == [(6, 2, [0, 1, 2, 3, 4, 5])]
    assert find_chains(norm, ["A"] * 6, allow_solo_cycles=False) == []


def test_repeated_one_message_cycle_is_not_reported_as_a_longer_cycle():
    assert find_chains(["hi"] * 4, ["A", "B", "A", "B"]) == [(4, 1, [0, 1, 2, 3])]


def test_one_unrelated_message_inside_a_chain_is_tolerated():
    chains = find_chains(["hi", "hi", "oops", "hi", "hi"], list("ABCAB"))
    assert chains == [(4, 1, [0, 1, 3, 4])]  # the interruption isn't a member


def test_tolerance_zero_means_no_leniency():
    assert find_chains(["hi", "hi", "oops", "hi", "hi"], list("ABCAB"), tolerance=0) == []


def test_two_unrelated_messages_in_a_row_end_the_chain():
    assert find_chains(["hi", "hi", "x1", "x2", "hi", "hi"], list("ABCDAB")) == []
    # ...unless tolerance is raised to cover them
    assert find_chains(["hi", "hi", "x1", "x2", "hi", "hi"], list("ABCDAB"), tolerance=2) == [
        (4, 1, [0, 1, 4, 5])]


def test_walks_backward_to_catch_a_chain_whose_first_cycle_was_interrupted():
    norm = ["gm all", "x", "good morning", "gm all", "good morning", "gm all", "good morning"]
    assert find_chains(norm, list("ABCABAB")) == [(6, 2, [0, 2, 3, 4, 5, 6])]


def test_fuzzy_matches_compare_to_the_original_not_the_previous_message():
    # each step is one typo from the previous one, but they drift away from
    # the original: hello -> hallo -> hxllo -> hxlxo
    chains = find_chains(["hello", "hallo", "hxllo", "hxlxo"], list("ABAB"))
    assert chains == [(3, 1, [0, 1, 2])]  # hxlxo is 2 typos from "hello"


def test_chains_dont_overlap_and_longest_comes_first():
    norm = ["a1", "a1", "a1", "zz", "bb22", "bb22", "bb22", "bb22", "bb22"]
    senders = list("ABAAABABA")
    assert find_chains(norm, senders) == [(5, 1, [4, 5, 6, 7, 8]), (3, 1, [0, 1, 2])]


def test_empty_entries_never_match():
    assert find_chains(["", "", "", ""], list("ABAB")) == []


def _verbatim_original(norm, senders, **kw):
    """The standalone find_chains.py's algorithm, kept verbatim (its global
    MIN_FUZZY_LEN fixed at the default 4) as the oracle for the refactor."""
    import types
    ns = types.SimpleNamespace(MIN_FUZZY_LEN=4)

    def sim(a, b):
        return similar(a, b, ns.MIN_FUZZY_LEN)

    n, candidates = len(norm), []
    for p in range(1, kw["max_cycle"] + 1):
        i = 0
        while i < n - p:
            first = norm[i]
            if not first:
                i += 1
                continue
            if not any(sim(first, norm[j]) for j in range(i + p, min(n, i + p + kw["tolerance"] + 1))):
                i += 1
                continue
            cycle = norm[i:i + p]
            if not all(cycle):
                i += 1
                continue
            members = list(range(i, i + p))
            pos, k = members[-1], p
            while True:
                expected, nxt = cycle[k % p], None
                for step in range(1, kw["tolerance"] + 2):
                    j = pos + step
                    if j >= n:
                        break
                    if sim(expected, norm[j]):
                        nxt = j
                        break
                if nxt is None:
                    break
                members.append(nxt)
                pos, k = nxt, k + 1
            if len(members) < 2 * p:
                i += 1
                continue
            back, pos, ph = [], members[0], p - 1
            while True:
                expected, prv = cycle[ph], None
                for step in range(1, kw["tolerance"] + 2):
                    j = pos - step
                    if j < 0:
                        break
                    if sim(expected, norm[j]):
                        prv = j
                        break
                if prv is None:
                    break
                back.append(prv)
                pos, ph = prv, (ph - 1) % p
            members = back[::-1] + members
            i = members[-1] + 1
            if len(members) < kw["min_length"] or not is_primitive(cycle):
                continue
            people = len({senders[m] for m in members})
            solo_ok = kw["allow_solo_cycles"] and people == 1 and p > 1
            if people >= kw["min_participants"] or solo_ok:
                candidates.append((len(members), p, members))
    candidates.sort(key=lambda c: (-c[0], c[1], c[2][0]))
    used, chosen = bytearray(n), []
    for count, p, members in candidates:
        a, b = members[0], members[-1] + 1
        if used.find(1, a, b) == -1:
            used[a:b] = b"\x01" * (b - a)
            chosen.append((count, p, members))
    return chosen


def test_refactored_find_chains_matches_the_original_algorithm():
    rng = random.Random(7)
    vocab = ["hi", "hey", "hello", "hallo", "helo", "lol ok", "lol okk", "nice one",
             "nice on", "", "yo yo", "what", "hmm okay", "hmm okya"]
    for _ in range(600):
        n = rng.randint(3, 40)
        norm = [rng.choice(vocab) for _ in range(n)]
        senders = [rng.choice("ABC") for _ in range(n)]
        kw = dict(max_cycle=rng.randint(1, 5), min_length=rng.randint(2, 5),
                  min_participants=rng.randint(1, 3), allow_solo_cycles=rng.random() < .5,
                  tolerance=rng.randint(0, 3))
        assert find_chains(norm, senders, **kw) == _verbatim_original(norm, senders, **kw), (norm, kw)


def test_compute_chain_stats_end_to_end_with_an_interruption():
    msgs = [("Alice", "morning"), ("Alice", "Hey!"), ("Bob", "hey"), ("Carl", "unrelated"),
            ("Alice", "HEY."), ("Bob", "hey"), ("Alice", "something else")]
    stats = compute_chain_stats(_df(msgs), cfg)
    assert stats["total_found"] == 1
    (chain,) = stats["chains"]
    assert chain["length"] == 4 and chain["cycle_length"] == 1 and chain["repetitions"] == 4
    assert chain["span"] == 5
    assert chain["duration_seconds"] == 4 * 60
    assert chain["participants"] == [{"name": "Alice", "count": 2}, {"name": "Bob", "count": 2}]
    assert chain["interruptions"] == {"count": 1, "by": [{"name": "Carl", "count": 1}]}
    assert chain["pattern"] == [{"sender": "Alice", "text": "Hey!"}]
    assert [(m["text"], m["interruption"]) for m in chain["messages"]] == [
        ("Hey!", False), ("hey", False), ("unrelated", True), ("HEY.", False), ("hey", False)]
    assert not chain["messages_truncated"]


def test_a_single_media_message_is_tolerated_but_two_in_a_row_break_the_chain():
    one = [("Alice", "lol ok"), ("Bob", "lol ok"), ("Alice", "<Media omitted>"),
           ("Bob", "lol ok"), ("Alice", "lol ok")]
    (chain,) = compute_chain_stats(_df(one), cfg)["chains"]
    assert chain["length"] == 4 and chain["interruptions"]["count"] == 1

    two = [("Alice", "lol ok"), ("Bob", "lol ok"), ("Alice", "<Media omitted>"),
           ("Bob", "<Media omitted>"), ("Alice", "lol ok"), ("Bob", "lol ok")]
    assert compute_chain_stats(_df(two), cfg)["chains"] == []


def test_system_rows_are_not_part_of_the_sequence():
    rows = [
        {"date_s": "01-Aug-2026", "time_s": "00:00", "sender": "Alice", "text": "yo yo", "is_system": False},
        {"date_s": "01-Aug-2026", "time_s": "00:01", "sender": "Bob", "text": "yo yo", "is_system": False},
        {"date_s": "01-Aug-2026", "time_s": "00:02", "sender": None, "text": "X added Y", "is_system": True},
        {"date_s": "01-Aug-2026", "time_s": "00:03", "sender": None, "text": "X added Z", "is_system": True},
        {"date_s": "01-Aug-2026", "time_s": "00:04", "sender": "Alice", "text": "yo yo", "is_system": False},
    ]
    (chain,) = compute_chain_stats(build_dataframe(rows), cfg)["chains"]
    assert chain["length"] == 3 and chain["interruptions"]["count"] == 0


def test_long_chain_messages_are_capped_but_length_is_not():
    msgs = [("Alice" if i % 2 else "Bob", "same thing") for i in range(60)]
    (chain,) = compute_chain_stats(_df(msgs), cfg)["chains"]
    assert chain["length"] == 60 and chain["span"] == 60
    assert len(chain["messages"]) == cfg.CHAIN_MAX_SHOWN_MESSAGES
    assert chain["messages_truncated"]


def test_format_duration():
    assert format_duration(30) == "30s"
    assert format_duration(252) == "4m 12s"
    assert format_duration(3900) == "1h 5m"
    assert format_duration(90000) == "1d 1h"
