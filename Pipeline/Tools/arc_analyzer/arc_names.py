"""
arc_names.py
============
Shared logic for the user-editable "ARC NAMES" table at the top of
arc_report.txt.

Only Arc and Mini-arc segments get a name — Filler periods aren't
individually interesting enough to bother naming, so they're skipped
everywhere in this module.

Two things read/write this table:
  - arc_analyzer.py, so a custom name/description survives the next
    time it regenerates arc_report.txt from scratch.
  - chat_analyzer's analyze_chat.py, so it can pick up whatever's
    CURRENTLY in arc_report.txt (even if it was hand-edited since the
    last time arc_analyzer.py ran) when it builds a separate report
    section for each arc/mini-arc.

Matching a name to "the same" arc/mini-arc across two different
readings of the file is done via each segment's `label` (e.g. "Arc 1",
"Mini-arc 3") — a chronological, per-type position that arc_analyzer.py
already assigns deterministically every run (see label_segments() in
arc_analyzer.py). As long as the number of arcs/mini-arcs a run finds
doesn't change, a given label always refers to the same real-world
period, so it's a stable join key between the NAMES table and whatever
new segments get detected next time.
"""
import re

NAMES_HEADER = "ARC NAMES"
DIVIDER = "=" * 60

_ARC_LINE_RE = re.compile(r"^arc\s+(\d+):\s*(.*)$")
_DESC_LINE_RE = re.compile(r"^\s*description:\s*(.*)$")
# The per-segment header lines in the main report body look like:
#   "Arc 1: 19-Jul-2026 01:17 -> 22-Aug-2026 23:59"
#   "Mini-arc 3 (\"Custom Name\"): 03-Jan-2026 ..."
# `label` is just the "Arc 1" / "Mini-arc 3" part.
_BODY_LABEL_RE = re.compile(r"^((?:Mini-arc|Arc)\s+\d+)\b")
_BODY_FILLER_RE = re.compile(r"^Filler\s+\d+\b")


def default_name(seg_type, per_type_index):
    """Default display name before any custom rename: 'arc-<n>' for a
    full Arc, 'Miniarc-<n>' for a Mini-arc, numbered by that segment's
    position among others of the SAME type only — so the first
    Mini-arc is 'Miniarc-1' even if an Arc came before it chronologically."""
    if seg_type == "arc":
        return f"arc-{per_type_index}"
    if seg_type == "miniarc":
        return f"Miniarc-{per_type_index}"
    return f"{seg_type}-{per_type_index}"  # shouldn't normally happen


def assign_names(all_segments, existing_names=None):
    """Attach 'name' and 'description' to every arc/miniarc segment in
    `all_segments` (each must already have 'label' set, e.g. by
    arc_analyzer.label_segments()). `existing_names`: optional
    {label: {"name": ..., "description": ...}}, typically from
    parse_report_names() on the PREVIOUS arc_report.txt — if a segment's
    label matches, its custom name/description carry over; otherwise it
    gets the default name and an empty description. Filler segments are
    left untouched (no 'name'/'description' keys added). Returns
    `all_segments` (mutated in place, also returned for convenience)."""
    existing_names = existing_names or {}
    per_type_counters = {"arc": 0, "miniarc": 0}
    for seg in all_segments:
        if seg["type"] not in ("arc", "miniarc"):
            continue
        per_type_counters[seg["type"]] += 1
        default = default_name(seg["type"], per_type_counters[seg["type"]])
        prior = existing_names.get(seg["label"])
        seg["name"] = (prior["name"].strip() if prior and prior.get("name", "").strip() else default)
        seg["description"] = prior["description"].strip() if prior else ""
    return all_segments


def parse_report_names(report_text):
    """Reads a previously-written arc_report.txt's full text and returns
    {label: {"name": ..., "description": ...}}, by pairing up the ARC
    NAMES table (top of the file, chronological order across arcs +
    mini-arcs only) with the body's own per-segment headers (which also
    include Filler, in the same chronological order — Filler lines are
    skipped so both lists line up). Returns {} if the file has no ARC
    NAMES table at all (e.g. it's from before this feature existed)."""
    lines = report_text.splitlines()

    # 1. Pull the ARC NAMES entries, in file order.
    names_in_order = []
    in_names = False
    pending = None
    for line in lines:
        if line.strip() == NAMES_HEADER:
            in_names = True
            continue
        if not in_names:
            continue
        if line.strip() == DIVIDER and names_in_order:
            break  # end of the ARC NAMES block (its opening divider is skipped above)
        m = _ARC_LINE_RE.match(line.strip())
        if m:
            if pending is not None:
                names_in_order.append(pending)
            pending = {"name": m.group(2).strip(), "description": ""}
            continue
        m = _DESC_LINE_RE.match(line)
        if m and pending is not None:
            pending["description"] = m.group(1).strip()
    if pending is not None:
        names_in_order.append(pending)

    if not names_in_order:
        return {}

    # 2. Pull body labels in the same order, arc/mini-arc only.
    labels_in_order = []
    for line in lines:
        stripped = line.strip()
        if _BODY_FILLER_RE.match(stripped):
            continue
        m = _BODY_LABEL_RE.match(stripped)
        if m:
            labels_in_order.append(m.group(1))

    # 3. Zip them together -- both lists are in the same chronological
    # order by construction (see render_names_section() / write_report()).
    return dict(zip(labels_in_order, names_in_order))


def render_names_section(all_segments):
    """The user-editable block written at the very top of arc_report.txt.
    Every segment in `all_segments` must already have 'name'/'description'
    set (see assign_names())."""
    nameable = [s for s in all_segments if s["type"] in ("arc", "miniarc")]
    lines = [
        NAMES_HEADER,
        DIVIDER,
        "Rename any arc or mini-arc below, and add a short description if",
        "you'd like -- both flow into the chat analyzer's PDF/HTML report,",
        "which builds a separate mini-report for each one. Leaving a name",
        "as the default (e.g. \"Miniarc-2\") is fine, it just uses that as",
        "the label.",
        "",
        "Edits here are preserved the next time this report regenerates,",
        "matched up by each arc/mini-arc's chronological position within",
        "its own type -- if the NUMBER of arcs or mini-arcs changes between",
        "runs, double-check the names still line up with the right period.",
        "",
    ]
    for i, seg in enumerate(nameable, start=1):
        lines.append(f"arc {i}: {seg['name']}")
        lines.append(f"  description: {seg['description']}")
    lines.append(DIVIDER)
    lines.append("")
    return "\n".join(lines)


def load_names_for_periods(periods, arc_report_path):
    """Convenience for readers OTHER than arc_analyzer.py (namely
    chat_analyzer's analyze_chat.py): given a list of period dicts that
    already have a 'label' key (e.g. rows loaded from arc_summary.json)
    and the path to the CURRENT arc_report.txt, fill in/overwrite each
    period's 'name' and 'description' from whatever is presently in the
    file. If the file is missing or has no ARC NAMES table, each
    period's existing 'name'/'description' (e.g. whatever was already
    baked into arc_summary.json) is left as-is. Mutates and returns
    `periods`."""
    import os
    if not arc_report_path or not os.path.isfile(arc_report_path):
        return periods
    with open(arc_report_path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    current = parse_report_names(text)
    for p in periods:
        entry = current.get(p.get("label"))
        if entry:
            if entry.get("name", "").strip():
                p["name"] = entry["name"].strip()
            p["description"] = entry.get("description", "").strip()
    return periods
