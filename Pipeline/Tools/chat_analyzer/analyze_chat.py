#!/usr/bin/env python3
"""
analyze_chat.py
================
Turns Full_Archive.txt into:
  - chat_report.html        (rich, interactive report — open in a browser)
  - chat_search_data.json   (data file the HTML report's search tools need —
                              keep it in the SAME folder as the .html file)
  - chat_report.pdf         (static, shareable version of the same report)

Basic usage:
    python3 analyze_chat.py
    python3 analyze_chat.py --input ../../../Full_Archive.txt --outdir .

By default this reads the repo's own Full_Archive.txt directly (no need to
copy it here first, and no need to run this from any particular folder)
and writes chat_report.html, chat_report.pdf, and chat_search_data.json
to Reports/ at the project root (created automatically), alongside every
other generated report. Chart images used to build those files are
cached in _chart_cache/ next to this script — that folder isn't a report
itself, just working files.

Edit chat_config.py first to plug in your own swear-word / laugh-word lists
and tune thresholds.

Custom slices (section / date-range / people / one-off threshold tweaks):
    # Only a PDF, only the words & fun-facts sections
    python3 analyze_chat.py --pdf-only --sections words,funfacts

    # Only March 2024, only two people, looser thresholds since it's a
    # much smaller slice than the full archive
    python3 analyze_chat.py --pdf-only --start-date 2024-03-01 --end-date 2024-03-31 \
        --people "Alice Smith,Bob Jones" --min-repeat-count 2 --min-word-length 4 \
        --out-name march_alice_bob

    # Skip the built-in "last N days" section, or change its size
    python3 analyze_chat.py --sections overview,timing,words
    python3 analyze_chat.py --last-period-days 60

    # Skip the built-in "Arcs & Mini-arcs" section (one mini-report per
    # arc/mini-arc from arc_report.txt — run arc_analyzer.py first to
    # populate it)
    python3 analyze_chat.py --sections overview,timing,words,lastperiod

Run `python3 analyze_chat.py --help` for the full flag list.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

import pandas as pd

from parsing import parse_chat_file, build_dataframe, get_participants
from stats_engine import (
    compute_overall, compute_time_distribution, compute_individual_stats,
    compute_word_stats, compute_phrase_stats, compute_leaderboards,
    compute_arc_signature_stats,
)
import chat_config as cfg
import chart_builder as cb
from html_report import build_html, SECTION_ORDER as HTML_SECTION_ORDER
from pdf_report import build_pdf
from search_export import build_search_data, write_search_json

# This file lives at Pipeline/Tools/chat_analyzer/analyze_chat.py, three
# folders below the repo root, where Full_Archive.txt lives.
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2]
DEFAULT_INPUT = REPO_ROOT / "Full_Archive.txt"
DEFAULT_OUTDIR = REPO_ROOT / "Reports"  # chat_report.html/.pdf + chat_search_data.json
CHART_CACHE_DIR = SCRIPT_DIR / "_chart_cache"  # intermediate PNGs only — not a final report

# arc_analyzer.py lives in the sibling Tools/arc_analyzer/ folder. Its
# arc_names.py module (parsing the editable "ARC NAMES" table in
# arc_report.txt) is shared rather than duplicated here — see the "Arcs
# & Mini-arcs" section below.
ARC_ANALYZER_DIR = SCRIPT_DIR.parent / "arc_analyzer"
sys.path.insert(0, str(ARC_ANALYZER_DIR))
import arc_names  # noqa: E402

DEFAULT_ARC_REPORT = REPO_ROOT / "Reports" / "arc_report.txt"
DEFAULT_ARC_SUMMARY = ARC_ANALYZER_DIR / "data" / "arc_summary.json"

# Section names accepted by --sections. Order here = order they're rendered in.
ALL_SECTIONS = HTML_SECTION_ORDER + ["lastperiod", "arcs"]


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def _filter_df(df, start=None, end=None, people=None):
    """Restrict the dataframe to a date range and/or a set of senders.
    System messages (joins/leaves/etc) are always kept when filtering by
    people, so streak/silence context around the conversation isn't lost —
    they're excluded from per-person stats anyway."""
    out = df
    if start is not None:
        out = out[out["timestamp"] >= pd.Timestamp(start)]
    if end is not None:
        end_ts = pd.Timestamp(end) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        out = out[out["timestamp"] <= end_ts]
    if people:
        keep = set(people)
        out = out[out["is_system"] | out["sender"].isin(keep)]
    return out.reset_index(drop=True)


def load_arc_segments(arc_summary_path, arc_report_path):
    """Reads arc_analyzer's arc_summary.json (segment boundaries — the
    structured, reliable source) and layers the CURRENT contents of
    arc_report.txt's editable "ARC NAMES" table on top (the live source
    for names/descriptions, since a person may have renamed something in
    that file after the last time arc_analyzer.py actually ran). Returns
    a list of dicts: {label, type, name, description, start, end,
    duration_days, n_messages}, Filler segments excluded, in
    chronological order. Returns [] if arc_summary.json doesn't exist
    yet (arc_analyzer.py hasn't been run)."""
    if not os.path.isfile(arc_summary_path):
        return []
    with open(arc_summary_path, "r", encoding="utf-8") as f:
        rows = json.load(f)
    segments = [r for r in rows if r.get("type") in ("arc", "miniarc")]
    # arc_summary.json already stores whatever name/description
    # arc_analyzer.py last wrote — used as a fallback below if
    # arc_report.txt is missing or doesn't mention a given label.
    arc_names.load_names_for_periods(segments, str(arc_report_path))
    return segments


def compute_bundle(df, participants, cfg_profile, log_label=""):
    """Runs the whole (non-chart) stats pipeline on a given dataframe +
    participant list + threshold profile, returning one dict bundle. Used
    for the main report, the built-in "last N days" section, and any
    custom CLI slice — they're all just different (df, participants, cfg)
    combos fed through the same pipeline."""
    prefix = f"[{log_label}] " if log_label else ""
    log(f"{prefix}Computing overall stats ...")
    overall = compute_overall(df)

    log(f"{prefix}Computing time-of-day / calendar distributions ...")
    timedist = compute_time_distribution(df)

    log(f"{prefix}Computing per-person stats ...")
    individual_stats, mention_pairs = compute_individual_stats(df, participants, overall["total_days_spanned"])

    log(f"{prefix}Computing leaderboards ...")
    lb = compute_leaderboards(individual_stats)

    log(f"{prefix}Computing most-repeated words ...")
    wordstats = compute_word_stats(df, participants, individual_stats, cfg=cfg_profile)

    log(f"{prefix}Computing most-repeated phrases ...")
    phrasestats = compute_phrase_stats(df, participants, individual_stats, cfg=cfg_profile)

    return {
        "overall": overall, "timedist": timedist, "individual_stats": individual_stats,
        "mention_pairs": mention_pairs, "lb": lb, "wordstats": wordstats,
        "phrasestats": phrasestats, "participants": participants,
    }


def build_charts(bundle, colors, prefix=""):
    """Renders every chart used by the report from a stats bundle, caching
    PNGs under CHART_CACHE_DIR/<prefix>chart_<name>.png. The prefix keeps
    the main report and the "last N days" section (which has its own
    bundle) from overwriting each other's chart files."""
    overall, timedist = bundle["overall"], bundle["timedist"]
    individual_stats, lb = bundle["individual_stats"], bundle["lb"]
    chart_paths = {}

    def chart(name, fn, *fn_args):
        path = os.path.join(CHART_CACHE_DIR, f"{prefix}chart_{name}.png")
        fn(*fn_args, path)
        chart_paths[name] = path

    chart("per_day", cb.chart_messages_per_day, timedist["per_day"])
    chart("by_hour", cb.chart_by_hour, timedist["by_hour"])
    chart("by_weekday", cb.chart_by_weekday, timedist["by_weekday"])
    chart("heatmap", cb.chart_heatmap, timedist["heatmap"])
    chart("by_month", cb.chart_by_month, timedist["by_month"])
    chart("most_msgs", cb.chart_leaderboard_bar, lb["most_messages"], "Most messages sent", "Messages", colors)
    chart("vocab", cb.chart_leaderboard_bar, lb["biggest_vocab"], "Biggest vocabulary", "Unique words", colors)
    chart("mentions", cb.chart_mentions_grouped, individual_stats, colors)
    chart("media", cb.chart_media_breakdown, overall)
    chart("hourly_sm", cb.chart_hourly_small_multiples, individual_stats, colors)
    # Same date range (first day -> last day of THIS bundle's own slice) for
    # every person's small-multiple, so someone who joined/went quiet
    # partway through reads as a flat 0 for that stretch instead of their
    # own chart silently rescaling to start at their first message.
    full_date_range = (overall["first_message_ts"][:10], overall["last_message_ts"][:10])
    chart("timeline_sm", cb.chart_timeline_small_multiples, individual_stats, colors, full_date_range)
    # NOTE: `chart()` appends the output path as the final positional arg,
    # matching every chart_builder function's signature (out_path is last).
    return chart_paths


def parse_sections(raw):
    if raw is None or raw.strip().lower() == "all":
        return list(ALL_SECTIONS)
    chosen = [s.strip().lower() for s in raw.split(",") if s.strip()]
    unknown = [s for s in chosen if s not in ALL_SECTIONS]
    if unknown:
        sys.exit(f"Unknown section(s): {', '.join(unknown)}. Valid options: {', '.join(ALL_SECTIONS)}, all")
    return chosen


def build_arg_parser():
    ap = argparse.ArgumentParser(
        description="Analyze a WhatsApp-style group chat export.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 analyze_chat.py
  python3 analyze_chat.py --pdf-only --sections words,funfacts
  python3 analyze_chat.py --pdf-only --start-date 2024-03-01 --end-date 2024-03-31 \\
      --people "Alice Smith,Bob Jones" --min-repeat-count 2 --min-word-length 4 \\
      --out-name march_alice_bob
  python3 analyze_chat.py --last-period-days 60
""")
    ap.add_argument("--input", default=str(DEFAULT_INPUT), help="Path to the chat .txt export")
    ap.add_argument("--outdir", default=str(DEFAULT_OUTDIR),
                     help="Where to write report files (default: Reports/ at the project root)")
    ap.add_argument("--min-messages", type=int, default=10,
                     help="Ignore senders with fewer than this many messages (default 10)")
    ap.add_argument("--out-name", default="chat_report",
                     help="Base filename (no extension) for the report(s) written, e.g. "
                          "'march_alice_bob' -> march_alice_bob.html / .pdf (default: chat_report)")

    slicing = ap.add_argument_group("Slicing (restrict what gets analyzed)")
    slicing.add_argument("--start-date", default=None, help="YYYY-MM-DD — only messages on/after this date")
    slicing.add_argument("--end-date", default=None, help="YYYY-MM-DD — only messages on/before this date")
    slicing.add_argument("--people", default=None,
                          help="Comma-separated exact sender names — restrict the WHOLE analysis to just "
                               "these people's messages (everyone else's messages are dropped)")

    sect = ap.add_argument_group("Section selection")
    sect.add_argument("--sections", default="all",
                       help=f"Comma-separated sections, or 'all' (default). Options: {', '.join(ALL_SECTIONS)}")

    out = ap.add_argument_group("Output control")
    out.add_argument("--pdf-only", action="store_true",
                      help="Skip the HTML report + search JSON, only write the PDF "
                           "(faster for one-off custom slices)")
    out.add_argument("--html-only", action="store_true",
                      help="Skip the PDF, only write the HTML report + search JSON")

    thresh = ap.add_argument_group("Threshold overrides (tweak the noise-filtering constants)")
    thresh.add_argument("--min-word-length", type=int, default=None,
                         help=f"Override MIN_WORD_LENGTH (default {cfg.MIN_WORD_LENGTH})")
    thresh.add_argument("--min-phrase-length", type=int, default=None,
                         help=f"Override MIN_PHRASE_LENGTH (default {cfg.MIN_PHRASE_LENGTH})")
    thresh.add_argument("--min-repeat-count", type=int, default=None,
                         help=f"Override MIN_REPEAT_COUNT (default {cfg.MIN_REPEAT_COUNT})")
    thresh.add_argument("--top-n", type=int, default=None,
                         help=f"Override TOP_N (default {cfg.TOP_N})")
    thresh.add_argument("--signature-min-messages", type=int, default=None,
                         help=f"Override SIGNATURE_MIN_MESSAGES (default {cfg.SIGNATURE_MIN_MESSAGES})")
    thresh.add_argument("--signature-top-n", type=int, default=None,
                         help=f"Override SIGNATURE_TOP_N_PER_PERSON (default {cfg.SIGNATURE_TOP_N_PER_PERSON})")

    lp = ap.add_argument_group("'Last N days' snapshot section")
    lp.add_argument("--last-period-days", type=int, default=cfg.LAST_PERIOD_DAYS,
                     help=f"Size in days of the built-in recent-snapshot section (default {cfg.LAST_PERIOD_DAYS}). "
                          f"Only rendered if 'lastperiod' is in --sections (it is, by default).")

    arcs = ap.add_argument_group("'Arcs & Mini-arcs' section")
    arcs.add_argument("--arc-summary", default=str(DEFAULT_ARC_SUMMARY),
                       help=f"Path to arc_analyzer's arc_summary.json, for arc/mini-arc date ranges "
                            f"(default: {DEFAULT_ARC_SUMMARY}). Only used if 'arcs' is in --sections "
                            f"(it is, by default).")
    arcs.add_argument("--arc-report", default=str(DEFAULT_ARC_REPORT),
                       help=f"Path to arc_report.txt, for the CURRENT custom names/descriptions "
                            f"(default: {DEFAULT_ARC_REPORT}). Re-read fresh on every run, so hand-edited "
                            f"names show up even without re-running arc_analyzer.py first.")
    return ap


def main():
    args = build_arg_parser().parse_args()

    if not os.path.exists(args.input):
        sys.exit(f"Could not find '{args.input}'. Pass --input <path> to point at the archive file.")
    if args.pdf_only and args.html_only:
        sys.exit("--pdf-only and --html-only can't both be set.")

    sections = parse_sections(args.sections)

    overrides = {}
    if args.min_word_length is not None:
        overrides["MIN_WORD_LENGTH"] = args.min_word_length
    if args.min_phrase_length is not None:
        overrides["MIN_PHRASE_LENGTH"] = args.min_phrase_length
    if args.min_repeat_count is not None:
        overrides["MIN_REPEAT_COUNT"] = args.min_repeat_count
    if args.top_n is not None:
        overrides["TOP_N"] = args.top_n
    if args.signature_min_messages is not None:
        overrides["SIGNATURE_MIN_MESSAGES"] = args.signature_min_messages
    if args.signature_top_n is not None:
        overrides["SIGNATURE_TOP_N_PER_PERSON"] = args.signature_top_n
    cfg_profile = cfg.make_profile(**overrides) if overrides else cfg
    if overrides:
        log(f"Threshold overrides in effect: {overrides}")

    os.makedirs(args.outdir, exist_ok=True)
    os.makedirs(CHART_CACHE_DIR, exist_ok=True)
    t_start = time.time()

    log(f"Reading {args.input} ...")
    records = parse_chat_file(args.input)
    log(f"Parsed {len(records):,} raw lines/messages.")
    df_full = build_dataframe(records)

    people_filter = [p.strip() for p in args.people.split(",") if p.strip()] if args.people else None
    custom_slice = bool(args.start_date or args.end_date or people_filter)

    df = _filter_df(df_full, args.start_date, args.end_date, people_filter)
    if len(df) == 0:
        sys.exit("That date range / people filter left zero messages — nothing to analyze. "
                  "Double check --start-date/--end-date/--people.")
    if custom_slice:
        log(f"Custom slice: {len(df):,} of {len(df_full):,} rows kept "
            f"(start={args.start_date or 'archive start'}, end={args.end_date or 'archive end'}, "
            f"people={', '.join(people_filter) if people_filter else 'everyone'})")

    participants = get_participants(df, min_messages=args.min_messages)
    if not participants:
        sys.exit(f"No one in this slice has {args.min_messages}+ messages, so there's "
                  f"nothing to build a per-person report from. Try a lower --min-messages, "
                  f"a wider date range, or check --people / --input.")
    log(f"Found {len(participants)} participants (>= {args.min_messages} messages each): {', '.join(participants)}")

    bundle = compute_bundle(df, participants, cfg_profile)

    log("Rendering charts ...")
    colors = cb.person_colors(participants)
    chart_paths = build_charts(bundle, colors)

    # ---- built-in "last N days" snapshot ----
    # A separate, self-contained mini re-run of the whole pipeline on just
    # the tail end of THIS run's own slice, with looser noise thresholds
    # (see LAST_PERIOD_* in chat_config.py) since it naturally has far
    # fewer messages than the full slice above.
    last_period = None
    if "lastperiod" in sections:
        days = args.last_period_days
        last_ts = pd.Timestamp(bundle["overall"]["last_message_ts"])
        lp_start = (last_ts - pd.Timedelta(days=days - 1)).date().isoformat()
        df_lp = _filter_df(df, start=lp_start)
        lp_participants = get_participants(df_lp, min_messages=1)
        if not lp_participants:
            log(f"Skipping 'last {days} days' section — no messages in that window.")
        else:
            lp_cfg = cfg.make_profile(
                MIN_WORD_LENGTH=cfg.LAST_PERIOD_MIN_WORD_LENGTH,
                MIN_PHRASE_LENGTH=cfg.LAST_PERIOD_MIN_PHRASE_LENGTH,
                MIN_REPEAT_COUNT=cfg.LAST_PERIOD_MIN_REPEAT_COUNT,
                TOP_N=cfg.LAST_PERIOD_TOP_N,
                SIGNATURE_MIN_MESSAGES=cfg.LAST_PERIOD_SIGNATURE_MIN_MESSAGES,
                SIGNATURE_TOP_N_PER_PERSON=cfg.LAST_PERIOD_SIGNATURE_TOP_N_PER_PERSON,
            )
            lp_bundle = compute_bundle(df_lp, lp_participants, lp_cfg, log_label=f"last {days}d")
            lp_colors = cb.person_colors(lp_participants)
            lp_charts = build_charts(lp_bundle, lp_colors, prefix="lp_")
            last_period = {"days": days, "bundle": lp_bundle, "charts": lp_charts, "cfg": lp_cfg}

    # ---- built-in "arcs & mini-arcs" section ----
    # Same idea as "last N days" above, but one self-contained mini
    # re-run per arc/mini-arc that arc_analyzer.py found in
    # arc_report.txt, instead of one fixed trailing window. Uses the
    # same loosened LAST_PERIOD_* thresholds for the same reason: each
    # arc/mini-arc is also a much smaller slice than the full archive.
    arc_periods = []
    if "arcs" in sections:
        segments = load_arc_segments(args.arc_summary, args.arc_report)
        if not segments:
            log(f"Skipping 'arcs' section — no {os.path.basename(str(args.arc_summary))} found. "
                f"Run arc_analyzer.py first to enable it.")
        else:
            arc_cfg = cfg.make_profile(
                MIN_WORD_LENGTH=cfg.LAST_PERIOD_MIN_WORD_LENGTH,
                MIN_PHRASE_LENGTH=cfg.LAST_PERIOD_MIN_PHRASE_LENGTH,
                MIN_REPEAT_COUNT=cfg.LAST_PERIOD_MIN_REPEAT_COUNT,
                TOP_N=cfg.LAST_PERIOD_TOP_N,
                SIGNATURE_MIN_MESSAGES=cfg.LAST_PERIOD_SIGNATURE_MIN_MESSAGES,
                SIGNATURE_TOP_N_PER_PERSON=cfg.LAST_PERIOD_SIGNATURE_TOP_N_PER_PERSON,
            )
            for i, seg in enumerate(segments, start=1):
                label = seg["label"]
                df_arc = _filter_df(df, start=seg["start"][:10], end=seg["end"][:10])
                arc_participants = get_participants(df_arc, min_messages=1)
                if not arc_participants:
                    log(f"Skipping {label} — no messages in that window.")
                    continue
                arc_bundle = compute_bundle(df_arc, arc_participants, arc_cfg, log_label=label)

                # Per-arc "signature words/phrases" are NOT the same
                # per-person breakdown as the main report's — that would
                # just be redundant with each person's own signature
                # words everywhere else. Instead, compare this arc's word/
                # phrase frequencies against the ENTIRE archive (`df`) to
                # find this arc's own topic fingerprint, and swap that in
                # for the per-person version compute_bundle computed above.
                arc_sig = compute_arc_signature_stats(df_arc, df, arc_participants, arc_cfg)
                arc_bundle["wordstats"]["signature_words"] = arc_sig["signature_words"]
                arc_bundle["phrasestats"]["signature_phrases"] = arc_sig["signature_phrases"]

                arc_colors = cb.person_colors(arc_participants)
                arc_charts = build_charts(arc_bundle, arc_colors, prefix=f"arc{i}_")
                arc_periods.append({
                    "label": label, "seg_type": seg["type"],
                    "name": seg.get("name") or label, "description": seg.get("description") or "",
                    "start_date": seg["start"][:10], "end_date": seg["end"][:10],
                    "duration_days": seg["duration_days"],
                    "bundle": arc_bundle, "charts": arc_charts, "cfg": arc_cfg,
                })
            if not arc_periods:
                log("Skipping 'arcs' section — every detected arc/mini-arc window had zero messages.")

    out_base = args.out_name
    html_path = pdf_path = json_path = None

    if not args.pdf_only:
        log("Writing HTML report ...")
        html_path = build_html(
            bundle["overall"], bundle["timedist"], bundle["individual_stats"], bundle["lb"],
            bundle["wordstats"], bundle["phrasestats"], bundle["mention_pairs"], chart_paths,
            bundle["participants"], os.path.join(args.outdir, f"{out_base}.html"),
            sections=sections, last_period=last_period, arc_periods=arc_periods, cfg_profile=cfg_profile,
        )
        log("Writing search data JSON (needed by the HTML report's Explorer tab) ...")
        search_data = build_search_data(df, bundle["participants"], bundle["individual_stats"],
                                         bundle["overall"], bundle["timedist"])
        json_path = os.path.join(args.outdir, "chat_search_data.json")
        write_search_json(search_data, json_path)

    if not args.html_only:
        log("Writing PDF report ...")
        pdf_path = build_pdf(
            bundle["overall"], bundle["individual_stats"], bundle["lb"], bundle["wordstats"],
            bundle["phrasestats"], bundle["mention_pairs"], chart_paths, bundle["participants"],
            os.path.join(args.outdir, f"{out_base}.pdf"),
            sections=sections, last_period=last_period, arc_periods=arc_periods, cfg_profile=cfg_profile,
        )

    elapsed = time.time() - t_start
    log(f"Done in {elapsed:.1f}s. Reports written to: {os.path.abspath(args.outdir)}")
    if html_path:
        log(f" - {os.path.basename(html_path)}  (open in a browser)")
    if json_path:
        log(f" - {os.path.basename(json_path)}  (must stay next to the .html file)")
    if pdf_path:
        log(f" - {os.path.basename(pdf_path)}  (shareable, static)")
    if arc_periods:
        log(f" - Arcs & Mini-arcs section: {len(arc_periods)} period(s) "
            f"({', '.join(p['name'] for p in arc_periods)})")
    if html_path:
        log("If the Explorer tab in the HTML report says it can't load data, run:")
        log(f"   cd {args.outdir} && python3 -m http.server 8000")
        log("   then open http://localhost:8000/{}".format(os.path.basename(html_path)))


if __name__ == "__main__":
    main()
