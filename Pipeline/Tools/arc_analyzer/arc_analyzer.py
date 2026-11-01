#!/usr/bin/env python3
"""
arc_analyzer.py
================

Analyzes Full_Archive.txt to find "Arcs" (sustained periods of high
message frequency), "Mini-arcs" (smaller/shorter spikes), and "Filler"
(everything else), then reports stats for each segment and plots the
rolling-average frequency curve with each segment marked.

Expected input line format (one message per line, WhatsApp-style export):

    19-Jul-2026, 01:17:49 - Alice: Cursed

Lines that don't match the "<date> - <sender>: <text>" pattern are treated
as a continuation of the previous message (e.g. multi-line texts).

By default this reads Full_Archive.txt from your data directory (see
Pipeline/omar_paths.py) and writes arc_report.txt and arc_timeline.png to
that directory's Reports/ folder, with arc_summary.csv/json in its
.cache/arc/ folder — no setup needed before running it.

arc_report.txt opens with an editable "ARC NAMES" table, one line per
arc/mini-arc, e.g. `arc 1: Miniarc-1`. Replace the text after the colon
to rename any of them, and fill in the "description:" line under it if
you'd like — both flow into chat_analyzer's PDF/HTML report, which
builds a separate mini-report for each arc/mini-arc (see arc_names.py).
Names/descriptions you set are preserved the next time this script
regenerates the report, matched to the same arc/mini-arc by its
chronological position within its own type.

Everything you'd want to tune is a setting in the CONFIG class below, and
the values in this file are generic defaults. To tune them for YOUR chat,
don't edit this file -- put an "arc_analyzer" section in your data
directory's config.json instead, e.g.

    {"arc_analyzer": {"ROLLING_WINDOW_DAYS": 21, "ARC_PEAK_MULTIPLIER": 1.5}}

Any setting named in CONFIG can be overridden that way (see
Pipeline/config.example.json).
"""

import re
import os
import sys
import json
import argparse
from pathlib import Path
from datetime import timedelta
from collections import defaultdict

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parents[1]))  # Pipeline/, for omar_paths
import omar_paths  # noqa: E402
import arc_names  # noqa: E402

try:
    _PATHS = omar_paths.get_paths()
except omar_paths.DataDirError as _e:
    sys.exit(str(_e))


# ============================================================================
# CONFIG -- everything you might want to tweak lives here.
# ============================================================================
class CONFIG:
    # --- I/O ---
    INPUT_FILE = str(_PATHS.archive)      # the archive, read directly
    OUTPUT_DIR = str(_PATHS.reports)      # arc_report.txt / arc_timeline.png go here
    CACHE_DIR = str(_PATHS.arc_data)      # arc_summary.csv/json go here (supplementary, not a final report)

    # --- Parsing ---
    # Matches: "19-Jul-2026, 01:17 - Alice: message text" (seconds optional,
    # for backward compatibility with any archive still in the older
    # HH:MM:SS format)
    LINE_REGEX = re.compile(
        r"^(?P<ts>\d{1,2}-[A-Za-z]{3}-\d{4}, \d{2}:\d{2}(?::\d{2})?)\s-\s"
        r"(?P<sender>[^:]+):\s(?P<text>.*)$"
    )
    DATE_FORMATS = ["%d-%b-%Y, %H:%M", "%d-%b-%Y, %H:%M:%S"]
    # normalize_export.py tags group events ("X added Y", "X changed the
    # subject"...) with this marker, and they're dropped here -- they're
    # not messages. This is matched against the SENDER field only, never
    # message text, so an ordinary message containing "left" or "added"
    # is never dropped.
    SYSTEM_SENDER_PREFIX = "[SYSTEM]"
    # --- Rolling average / baseline ---
    ROLLING_WINDOW_DAYS = 14      # rolling-average window, in days
    ROLLING_CENTERED = True       # center the rolling window on each day

    # --- Local maxima detection ---
    # A day is a local maximum if its rolling value is the max within
    # +/- LOCAL_MAX_ORDER_DAYS of itself.
    LOCAL_MAX_ORDER_DAYS = 4
    # Minimum height (as a multiple of the whole-GC mean) for a local max
    # to be considered a candidate spike at all.
    MIN_PEAK_MULTIPLIER = 1.2

    # --- Region growing (walking outward from a peak) ---
    # "Back to usual" = rolling average has returned to within this
    # multiple of the whole-GC mean.
    RETURN_TO_BASELINE_MULTIPLIER = 1.05

    # --- Arc vs Mini-arc classification ---
    ARC_PEAK_MULTIPLIER = 2.0     # peak must be >= this * mean to be a full Arc
    ARC_MIN_DURATION_DAYS = 28    # ...and last at least this many days
    # Anything that cleared MIN_PEAK_MULTIPLIER but didn't qualify as an
    # Arc becomes a Mini-arc automatically.

    # --- Merging nearby regions ---
    # Two detected regions separated by less than this many days get
    # merged into a single region before classification.
    MERGE_GAP_DAYS = 1

    # --- Per-segment stats ---
    TOP_N_CONTRIBUTORS = 3        # most active senders shown per segment
    TOP_N_DISTINCTIVE = 5         # "punches above their weight" senders
    MIN_MESSAGES_FOR_DISTINCTIVE = 5   # ignore low-volume senders for that calc

    # --- Plot styling ---
    FIGSIZE = (18, 8)
    ARC_COLOR = "crimson"
    MINIARC_COLOR = "darkorange"
    ROLLING_LINE_COLOR = "steelblue"
    MEAN_LINE_COLOR = "gray"
    DPI = 150


def _apply_user_overrides():
    """Overrides CONFIG settings from the "arc_analyzer" section of the
    data directory's config.json. Unknown names are an error (a typo
    should be loud, not silently ignored)."""
    try:
        overrides = omar_paths.user_config_section("arc_analyzer")
    except omar_paths.DataDirError as e:
        sys.exit(str(e))
    for name, value in overrides.items():
        if not name.isupper() or not hasattr(CONFIG, name):
            sys.exit(f"config.json: unknown arc_analyzer setting '{name}'. "
                     f"Valid names are the UPPER_CASE settings in CONFIG "
                     f"(Pipeline/Tools/arc_analyzer/arc_analyzer.py).")
        if name == "FIGSIZE" and isinstance(value, list):
            value = tuple(value)
        setattr(CONFIG, name, value)


_apply_user_overrides()


# ============================================================================
# PARSING
# ============================================================================
def parse_chat(filepath):
    """Parse the raw export into a list of dicts: timestamp, sender, text."""
    messages = []
    current = None

    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        for raw_line in f:
            line = raw_line.rstrip("\n").rstrip("\r")
            if not line.strip():
                continue

            m = CONFIG.LINE_REGEX.match(line)
            if m:
                ts_str, sender, text = m.group("ts"), m.group("sender").strip(), m.group("text")

                if sender.startswith(CONFIG.SYSTEM_SENDER_PREFIX):
                    current = None  # don't let continuation lines attach to a dropped system msg
                    continue

                ts = None
                for fmt in CONFIG.DATE_FORMATS:
                    try:
                        ts = pd.to_datetime(ts_str, format=fmt)
                        break
                    except ValueError:
                        continue
                if ts is None:
                    current = None
                    continue

                current = {"timestamp": ts, "sender": sender, "text": text}
                messages.append(current)
            else:
                # continuation of the previous message's text
                if current is not None:
                    current["text"] += "\n" + line

    if not messages:
        raise ValueError("No messages parsed. Check LINE_REGEX / DATE_FORMAT against your export.")

    df = pd.DataFrame(messages)
    df.sort_values("timestamp", kind="stable", inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


# ============================================================================
# FREQUENCY / ROLLING AVERAGE
# ============================================================================
def build_daily_series(df):
    """Return a Series indexed by every calendar day in range, message count."""
    df["date"] = df["timestamp"].dt.floor("D")
    counts = df.groupby("date").size()
    full_range = pd.date_range(counts.index.min(), counts.index.max(), freq="D")
    daily = counts.reindex(full_range, fill_value=0)
    daily.index.name = "date"
    return daily


def compute_rolling(daily):
    window = CONFIG.ROLLING_WINDOW_DAYS
    return daily.rolling(window=window, center=CONFIG.ROLLING_CENTERED, min_periods=1).mean()


# ============================================================================
# LOCAL MAXIMA + REGION GROWING
# ============================================================================
def find_local_maxima(rolling, order, min_value):
    """Indices (positions) that are the max within +/- order of themselves,
    and clear min_value."""
    vals = rolling.values
    n = len(vals)
    peaks = []
    for i in range(n):
        if vals[i] < min_value:
            continue
        lo, hi = max(0, i - order), min(n, i + order + 1)
        window_vals = vals[lo:hi]
        if vals[i] == window_vals.max():
            peaks.append(i)
    # de-duplicate flat plateaus: collapse consecutive/close indices, keep first
    deduped = []
    for p in peaks:
        if deduped and p - deduped[-1] <= order:
            continue
        deduped.append(p)
    return deduped


def grow_region(rolling, peak_idx, baseline_threshold):
    """Walk left/right from peak_idx while rolling stays above threshold."""
    vals = rolling.values
    n = len(vals)
    left = peak_idx
    while left - 1 >= 0 and vals[left - 1] > baseline_threshold:
        left -= 1
    right = peak_idx
    while right + 1 < n and vals[right + 1] > baseline_threshold:
        right += 1
    return left, right


def merge_regions(regions, merge_gap_days):
    """regions: list of (start_idx, end_idx, peak_value). Merge overlapping
    or close-together regions. Index units are days (integer), so gap in
    days == index difference."""
    if not regions:
        return []
    regions = sorted(regions, key=lambda r: r[0])
    merged = [list(regions[0])]
    for start, end, peak in regions[1:]:
        last = merged[-1]
        if start - last[1] <= merge_gap_days:
            last[1] = max(last[1], end)
            last[2] = max(last[2], peak)
        else:
            merged.append([start, end, peak])
    return [tuple(r) for r in merged]


def detect_segments(daily, rolling, mean_baseline):
    """Returns list of dicts: {type, start_idx, end_idx, peak_value}
    type in {'arc', 'miniarc'} for detected spikes (filler computed later)."""
    min_peak_val = CONFIG.MIN_PEAK_MULTIPLIER * mean_baseline
    return_threshold = CONFIG.RETURN_TO_BASELINE_MULTIPLIER * mean_baseline

    peak_indices = find_local_maxima(rolling, CONFIG.LOCAL_MAX_ORDER_DAYS, min_peak_val)

    raw_regions = []
    for p in peak_indices:
        left, right = grow_region(rolling, p, return_threshold)
        raw_regions.append((left, right, rolling.values[p]))

    merged = merge_regions(raw_regions, CONFIG.MERGE_GAP_DAYS)

    segments = []
    for start_idx, end_idx, peak_val in merged:
        duration_days = end_idx - start_idx + 1
        is_arc = (
            peak_val >= CONFIG.ARC_PEAK_MULTIPLIER * mean_baseline
            and duration_days >= CONFIG.ARC_MIN_DURATION_DAYS
        )
        segments.append({
            "type": "arc" if is_arc else "miniarc",
            "start_idx": start_idx,
            "end_idx": end_idx,
            "peak_value": peak_val,
        })

    segments.sort(key=lambda s: s["start_idx"])
    return segments


def fill_gaps_with_filler(segments, n_days):
    """Given non-overlapping arc/miniarc segments (sorted), fill every gap
    (including before the first and after the last) with 'filler' segments."""
    all_segments = []
    cursor = 0
    for seg in segments:
        if seg["start_idx"] > cursor:
            all_segments.append({
                "type": "filler",
                "start_idx": cursor,
                "end_idx": seg["start_idx"] - 1,
                "peak_value": None,
            })
        all_segments.append(seg)
        cursor = seg["end_idx"] + 1
    if cursor <= n_days - 1:
        all_segments.append({
            "type": "filler",
            "start_idx": cursor,
            "end_idx": n_days - 1,
            "peak_value": None,
        })
    return all_segments


def label_segments(all_segments, daily_index):
    """Attach chronological per-type labels and real dates."""
    counters = defaultdict(int)
    for seg in all_segments:
        counters[seg["type"]] += 1
        label_map = {"arc": "Arc", "miniarc": "Mini-arc", "filler": "Filler"}
        seg["label"] = f"{label_map[seg['type']]} {counters[seg['type']]}"
        seg["start_date"] = daily_index[seg["start_idx"]]
        # end date is end of that calendar day
        seg["end_date"] = daily_index[seg["end_idx"]] + timedelta(hours=23, minutes=59, seconds=59)
    return all_segments


# ============================================================================
# PER-SEGMENT STATS
# ============================================================================
def compute_segment_stats(df, seg, daily, global_sender_counts, global_total_msgs):
    mask = (df["timestamp"] >= seg["start_date"]) & (df["timestamp"] <= seg["end_date"])
    sub = df.loc[mask]

    duration_days = seg["end_idx"] - seg["start_idx"] + 1
    n_msgs = len(sub)
    avg_per_day = n_msgs / duration_days if duration_days else 0.0

    # top contributors
    sender_counts = sub["sender"].value_counts()
    top_contributors = list(sender_counts.head(CONFIG.TOP_N_CONTRIBUTORS).items())

    # distinctive contributors: share here vs share in rest of the GC
    distinctive = []
    if n_msgs > 0:
        rest_total = global_total_msgs - n_msgs
        for sender, cnt in sender_counts.items():
            if cnt < CONFIG.MIN_MESSAGES_FOR_DISTINCTIVE:
                continue
            share_here = cnt / n_msgs
            cnt_rest = global_sender_counts.get(sender, 0) - cnt
            share_rest = (cnt_rest / rest_total) if rest_total > 0 else 0.0
            distinctive.append((sender, share_here - share_rest, cnt))
        distinctive.sort(key=lambda x: x[1], reverse=True)
        distinctive = distinctive[:CONFIG.TOP_N_DISTINCTIVE]

    # peak day within segment
    seg_daily = daily.loc[seg["start_date"].floor("D"): seg["end_date"].floor("D")]
    peak_day = seg_daily.idxmax() if len(seg_daily) else None
    peak_day_count = int(seg_daily.max()) if len(seg_daily) else 0

    return {
        "n_messages": n_msgs,
        "duration_days": duration_days,
        "avg_per_day": avg_per_day,
        "top_contributors": top_contributors,
        "distinctive_contributors": distinctive,
        "peak_day": peak_day,
        "peak_day_count": peak_day_count,
    }


# ============================================================================
# OUTPUT
# ============================================================================
def write_report(all_segments, mean_baseline, outdir):
    lines = []
    # The user-editable naming table goes first, right at the top, so
    # it's the first thing anyone opening this file sees and edits.
    lines.append(arc_names.render_names_section(all_segments))

    lines.append("GC ARC ANALYSIS REPORT")
    lines.append("=" * 60)
    lines.append(f"Whole-GC mean messages/day (baseline): {mean_baseline:.2f}")
    lines.append("")

    for seg in all_segments:
        s = seg["stats"]
        header = f"{seg['label']}: {seg['start_date']:%d-%b-%Y %H:%M} -> {seg['end_date']:%d-%b-%Y %H:%M}"
        if seg["type"] in ("arc", "miniarc"):
            header = f"{seg['label']} (\"{seg['name']}\"): {seg['start_date']:%d-%b-%Y %H:%M} -> {seg['end_date']:%d-%b-%Y %H:%M}"
        lines.append(header)
        if seg["type"] in ("arc", "miniarc") and seg["description"]:
            lines.append(f"  description:    {seg['description']}")
        lines.append(f"  duration:        {s['duration_days']} days")
        lines.append(f"  messages:        {s['n_messages']}")
        lines.append(f"  avg msgs/day:    {s['avg_per_day']:.2f}  (baseline {mean_baseline:.2f})")
        if s["peak_day"] is not None:
            lines.append(f"  peak day:        {s['peak_day']:%d-%b-%Y} ({s['peak_day_count']} messages)")
        if s["top_contributors"]:
            top_str = ", ".join(f"{name} ({cnt})" for name, cnt in s["top_contributors"])
            lines.append(f"  top contributors:{' ' if len(top_str)<1 else ' '}{top_str}")
        if s["distinctive_contributors"]:
            dist_str = ", ".join(f"{name} (+{diff*100:.1f}pp, {cnt} msgs)" for name, diff, cnt in s["distinctive_contributors"])
            lines.append(f"  distinctive:     {dist_str}")
        lines.append("")

    report_text = "\n".join(lines)
    path = os.path.join(outdir, "arc_report.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(report_text)
    return path, report_text


def write_csv_json(all_segments, outdir):
    rows = []
    for seg in all_segments:
        s = seg["stats"]
        rows.append({
            "label": seg["label"],
            "type": seg["type"],
            "name": seg.get("name"),
            "description": seg.get("description"),
            "start": seg["start_date"].isoformat(),
            "end": seg["end_date"].isoformat(),
            "duration_days": s["duration_days"],
            "n_messages": s["n_messages"],
            "avg_per_day": round(s["avg_per_day"], 3),
            "peak_day": s["peak_day"].isoformat() if s["peak_day"] is not None else None,
            "peak_day_count": s["peak_day_count"],
            "top_contributors": s["top_contributors"],
            "distinctive_contributors": s["distinctive_contributors"],
        })
    csv_path = os.path.join(outdir, "arc_summary.csv")
    pd.DataFrame(rows).drop(columns=["top_contributors", "distinctive_contributors"]).to_csv(csv_path, index=False)

    json_path = os.path.join(outdir, "arc_summary.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, default=str)

    return csv_path, json_path


def plot_timeline(daily, rolling, mean_baseline, all_segments, outdir):
    fig, ax = plt.subplots(figsize=CONFIG.FIGSIZE)

    ax.plot(rolling.index, rolling.values, color=CONFIG.ROLLING_LINE_COLOR,
            linewidth=1.5, label=f"{CONFIG.ROLLING_WINDOW_DAYS}-day rolling avg msgs/day")
    ax.axhline(mean_baseline, color=CONFIG.MEAN_LINE_COLOR, linestyle="--",
               linewidth=1, label=f"GC mean ({mean_baseline:.1f}/day)")

    arc_label_done, mini_label_done = False, False
    for seg in all_segments:
        if seg["type"] == "arc":
            color = CONFIG.ARC_COLOR
            label = "Arc boundary" if not arc_label_done else None
            arc_label_done = True
        elif seg["type"] == "miniarc":
            color = CONFIG.MINIARC_COLOR
            label = "Mini-arc boundary" if not mini_label_done else None
            mini_label_done = True
        else:
            continue  # don't clutter the plot with filler lines
        ax.axvline(seg["start_date"], color=color, linestyle=":", linewidth=1.3, label=label)
        ax.axvline(seg["end_date"], color=color, linestyle=":", linewidth=1.3)
        ax.axvspan(seg["start_date"], seg["end_date"], color=color, alpha=0.08)
        # annotate with the segment's label AND its (possibly custom,
        # possibly still-default) name, e.g. 'Arc 1: "Exam Season"' --
        # seg["name"] already reflects whatever's currently in
        # arc_report.txt's ARC NAMES table, carried over by
        # arc_names.assign_names() before we ever get here, so a hand-typed
        # rename shows up on the chart the very next time this regenerates,
        # and a brand-new segment just shows its generic default name
        # (e.g. "Miniarc-3") until someone edits arc_report.txt by hand.
        annotation = f'{seg["label"]}: "{seg["name"]}"'
        ax.text(seg["start_date"], ax.get_ylim()[1] * 0.97, annotation,
                rotation=90, fontsize=7, va="top", ha="right", color=color)

    ax.set_title("Group Chat Message Frequency — Arcs & Mini-arcs")
    ax.set_xlabel("Date")
    ax.set_ylabel("Messages / day (rolling average)")
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    fig.autofmt_xdate()
    ax.legend(loc="upper right", fontsize=8)
    fig.tight_layout()

    path = os.path.join(outdir, "arc_timeline.png")
    fig.savefig(path, dpi=CONFIG.DPI)
    plt.close(fig)
    return path


# ============================================================================
# MAIN
# ============================================================================
def main():
    parser = argparse.ArgumentParser(description="Detect Arcs/Mini-arcs/Filler in a group chat export.")
    parser.add_argument("input_file", nargs="?", default=CONFIG.INPUT_FILE)
    parser.add_argument("-o", "--outdir", default=CONFIG.OUTPUT_DIR,
                         help="Where arc_report.txt and arc_timeline.png go (default: Reports/ in your data directory)")
    parser.add_argument("--cache-dir", default=CONFIG.CACHE_DIR,
                         help="Where arc_summary.csv/json go (default: .cache/arc/ in your data directory)")
    args = parser.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    os.makedirs(args.cache_dir, exist_ok=True)

    if not os.path.isfile(args.input_file):
        sys.exit(f"Input file not found: {args.input_file}\n"
                  f"Pass a path as the first argument to use a different file, e.g.:\n"
                  f"  python3 arc_analyzer.py path/to/Full_Archive.txt")

    print(f"Parsing {args.input_file} ...")
    df = parse_chat(args.input_file)
    print(f"  parsed {len(df):,} messages from {df['timestamp'].min()} to {df['timestamp'].max()}")

    daily = build_daily_series(df)
    rolling = compute_rolling(daily)
    mean_baseline = daily.mean()
    print(f"  whole-GC mean: {mean_baseline:.2f} messages/day over {len(daily)} days")

    spike_segments = detect_segments(daily, rolling, mean_baseline)
    all_segments = fill_gaps_with_filler(spike_segments, len(daily))
    all_segments = label_segments(all_segments, daily.index)

    # Carry over any custom arc/mini-arc names + descriptions from
    # whatever's CURRENTLY at the report output path (which may have been
    # hand-edited since the last run) before we overwrite it.
    existing_report_path = os.path.join(args.outdir, "arc_report.txt")
    existing_names = {}
    if os.path.isfile(existing_report_path):
        with open(existing_report_path, "r", encoding="utf-8", errors="replace") as f:
            existing_names = arc_names.parse_report_names(f.read())
    all_segments = arc_names.assign_names(all_segments, existing_names)

    print(f"  found {sum(1 for s in all_segments if s['type']=='arc')} arcs, "
          f"{sum(1 for s in all_segments if s['type']=='miniarc')} mini-arcs, "
          f"{sum(1 for s in all_segments if s['type']=='filler')} filler segments")

    # global stats needed for the "distinctive contributors" comparison
    global_sender_counts = df["sender"].value_counts().to_dict()
    global_total_msgs = len(df)

    for seg in all_segments:
        seg["stats"] = compute_segment_stats(
            df, seg, daily, global_sender_counts, global_total_msgs,
        )

    report_path, report_text = write_report(all_segments, mean_baseline, args.outdir)
    csv_path, json_path = write_csv_json(all_segments, args.cache_dir)
    plot_path = plot_timeline(daily, rolling, mean_baseline, all_segments, args.outdir)

    print("\n" + report_text[:2000] + ("\n... (truncated, see file) ..." if len(report_text) > 2000 else ""))
    print(f"\nWrote:\n  {report_path}\n  {csv_path}\n  {json_path}\n  {plot_path}")


if __name__ == "__main__":
    main()