"""
Generates every chart as a PNG (used by both the HTML report, embedded as
base64, and the PDF report, embedded as an image). One consistent visual
style across all charts.
"""
import math
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import FancyBboxPatch

# ---- palette: "chat-log" theme -----------------------------------------
BG = "#FAF7F0"
INK = "#22252B"
MUTED = "#8A8574"
TEAL = "#1F6F63"
CORAL = "#E4572E"
GOLD = "#D9A441"
BLUE = "#3E6C9E"
PLUM = "#7A5C7E"
GRID = "#E4DFD1"

PALETTE = [TEAL, CORAL, GOLD, BLUE, PLUM, "#8FA876", "#B8564A", "#5B8A9E", "#C98A3F", "#6E6A8C",
           "#3F8F7A", "#C4693F"]

plt.rcParams.update({
    "figure.facecolor": BG,
    "axes.facecolor": BG,
    "savefig.facecolor": BG,
    "text.color": INK,
    "axes.edgecolor": GRID,
    "axes.labelcolor": INK,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "axes.grid": True,
    "grid.color": GRID,
    "grid.linewidth": 0.8,
    "font.size": 11,
    "font.family": "DejaVu Sans",
    "axes.titleweight": "bold",
    "axes.titlesize": 13,
    "axes.spines.top": False,
    "axes.spines.right": False,
})


def _save(fig, path):
    fig.savefig(path, dpi=150, bbox_inches="tight", pad_inches=0.35)
    plt.close(fig)


def _save_empty_chart(out_path, message):
    """Renders a small placeholder image with a centered message, instead
    of a real chart, for edge cases where there's nothing to plot (e.g. no
    participant cleared the --min-messages threshold)."""
    fig, ax = plt.subplots(figsize=(6, 2))
    ax.axis("off")
    ax.text(0.5, 0.5, message, ha="center", va="center", fontsize=11, color=MUTED, wrap=True)
    _save(fig, out_path)


def person_colors(names):
    return {n: PALETTE[i % len(PALETTE)] for i, n in enumerate(names)}


def chart_messages_per_day(per_day, out_path):
    import pandas as pd
    s = pd.Series(per_day).sort_index()
    s.index = pd.to_datetime(s.index)
    rolling = s.rolling(7, min_periods=1).mean()

    fig, ax = plt.subplots(figsize=(11, 4.2))
    ax.bar(s.index, s.values, width=1.0, color=TEAL, alpha=0.28, label="Messages / day")
    ax.plot(rolling.index, rolling.values, color=CORAL, linewidth=2, label="7-day average")
    ax.set_title("Messages per day, over the life of the group chat")
    ax.set_ylabel("Messages")
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
    ax.legend(frameon=False, loc="upper left")
    _save(fig, out_path)


def chart_by_hour(by_hour, out_path):
    hours = list(range(24))
    vals = [by_hour.get(h, 0) for h in hours]
    fig, ax = plt.subplots(figsize=(9, 3.8))
    colors = [CORAL if v == max(vals) else TEAL for v in vals]
    ax.bar(hours, vals, color=colors, width=0.75)
    ax.set_title("When the group chat is active — messages by hour of day")
    ax.set_xlabel("Hour (24h)")
    ax.set_ylabel("Messages")
    ax.set_xticks(hours)
    ax.set_xticklabels([f"{h:02d}" for h in hours], fontsize=8)
    _save(fig, out_path)


def chart_by_weekday(by_weekday, out_path):
    order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    vals = [by_weekday.get(d, 0) for d in order]
    fig, ax = plt.subplots(figsize=(8, 3.8))
    colors = [CORAL if v == max(vals) else BLUE for v in vals]
    ax.bar([d[:3] for d in order], vals, color=colors, width=0.6)
    ax.set_title("Messages by day of the week")
    ax.set_ylabel("Messages")
    _save(fig, out_path)


def chart_heatmap(heatmap, out_path):
    arr = np.array(heatmap)
    fig, ax = plt.subplots(figsize=(11, 3.6))
    im = ax.imshow(arr, aspect="auto", cmap="YlOrBr")
    ax.set_yticks(range(7))
    ax.set_yticklabels(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])
    ax.set_xticks(range(24))
    ax.set_xticklabels([f"{h:02d}" for h in range(24)], fontsize=8)
    ax.set_title("Activity heatmap — day of week vs hour of day")
    ax.grid(False)
    cbar = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.01)
    cbar.set_label("Messages", fontsize=9)
    _save(fig, out_path)


def chart_by_month(by_month, out_path):
    items = sorted(by_month.items())
    labels = [k for k, _ in items]
    vals = [v for _, v in items]
    fig, ax = plt.subplots(figsize=(11, 3.8))
    ax.bar(labels, vals, color=GOLD)
    ax.set_title("Messages per month")
    ax.set_ylabel("Messages")
    step = max(1, len(labels) // 18)
    ax.set_xticks(range(0, len(labels), step))
    ax.set_xticklabels([labels[i] for i in range(0, len(labels), step)], rotation=60, ha="right", fontsize=8)
    _save(fig, out_path)


def chart_leaderboard_bar(rows, title, xlabel, colors_map, out_path, fmt=None):
    """rows: list of {'person':..., 'value':...} already sorted desc."""
    rows = rows[:15]
    names = [r["person"] for r in rows][::-1]
    vals = [r["value"] for r in rows][::-1]
    colors = [colors_map.get(n, TEAL) if colors_map else TEAL for n in names]
    fig, ax = plt.subplots(figsize=(9, max(2.6, 0.42 * len(names))))
    bars = ax.barh(names, vals, color=colors)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    maxv = max(vals) if vals else 1
    for b, v in zip(bars, vals):
        label = fmt(v) if fmt else str(v)
        ax.text(b.get_width() + maxv * 0.015, b.get_y() + b.get_height() / 2, label,
                 va="center", fontsize=9, color=INK)
    ax.set_xlim(0, maxv * 1.18 if maxv else 1)
    _save(fig, out_path)


def chart_mentions_grouped(individual_stats, colors_map, out_path):
    people = list(individual_stats.keys())
    people = sorted(people, key=lambda p: -(individual_stats[p]["mentions_given"] + individual_stats[p]["mentions_received"]))[:15]
    given = [individual_stats[p]["mentions_given"] for p in people]
    received = [individual_stats[p]["mentions_received"] for p in people]

    y = np.arange(len(people))
    h = 0.38
    fig, ax = plt.subplots(figsize=(9, max(2.8, 0.5 * len(people))))
    ax.barh(y + h / 2, given, height=h, color=TEAL, label="Tags given")
    ax.barh(y - h / 2, received, height=h, color=CORAL, label="Tags received")
    ax.set_yticks(y)
    ax.set_yticklabels(people)
    ax.invert_yaxis()
    ax.set_title("Who tags others most vs who gets tagged most")
    ax.legend(frameon=False)
    _save(fig, out_path)


def chart_media_breakdown(overall, out_path):
    labels = ["Text", "Media", "Deleted", "Edited", "Calls"]
    vals = [overall["total_text_messages"], overall["total_media"], overall["total_deleted"],
            overall["total_edited"], overall["total_calls"]]
    colors = [TEAL, GOLD, CORAL, BLUE, PLUM]
    fig, ax = plt.subplots(figsize=(7, 3.8))
    bars = ax.bar(labels, vals, color=colors)
    ax.set_title("Message type breakdown")
    ax.set_ylabel("Count")
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v, f"{v:,}", ha="center", va="bottom", fontsize=9)
    _save(fig, out_path)


def chart_hourly_small_multiples(individual_stats, colors_map, out_path):
    people = list(individual_stats.keys())
    n = len(people)
    if n == 0:
        _save_empty_chart(out_path, "No participants met the --min-messages threshold")
        return
    cols = 4
    rows = math.ceil(n / cols)
    fig, axes = plt.subplots(rows, cols, figsize=(cols * 2.6, rows * 1.9), sharex=True)
    axes = np.array(axes).reshape(-1)
    for i, p in enumerate(people):
        ax = axes[i]
        hd = individual_stats[p]["hourly_distribution"]
        vals = [hd.get(str(h), hd.get(h, 0)) for h in range(24)]
        color = colors_map.get(p, TEAL) if colors_map else TEAL
        ax.bar(range(24), vals, color=color, width=1.0)
        ax.set_title(p, fontsize=9)
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)
    for j in range(n, len(axes)):
        axes[j].axis("off")
    fig.suptitle("Each person's hourly activity fingerprint", y=1.02, fontweight="bold")
    fig.tight_layout()
    _save(fig, out_path)


def chart_timeline_small_multiples(individual_stats, colors_map, date_range, out_path):
    """date_range: optional (first_day, last_day) covering the WHOLE group
    chat (not just this person's own active span). When given, every
    person's panel is reindexed onto that same full date range with missing
    days filled as 0 messages, and all panels share the same x-axis limits.
    This means someone who joined late or went quiet for a stretch shows a
    flat line at 0 for that period instead of their panel silently
    rescaling to start at their own first/last message."""
    import pandas as pd
    people = list(individual_stats.keys())
    n = len(people)
    if n == 0:
        _save_empty_chart(out_path, "No participants met the --min-messages threshold")
        return

    full_index = None
    if date_range:
        full_index = pd.date_range(date_range[0], date_range[1], freq="D")

    cols = 2
    rows = math.ceil(n / cols)
    fig, axes = plt.subplots(rows, cols, figsize=(cols * 5.6, rows * 1.6), sharex=(full_index is not None))
    axes = np.array(axes).reshape(-1)
    for i, p in enumerate(people):
        ax = axes[i]
        tl = individual_stats[p]["messages_per_day_timeline"]
        s = pd.Series(tl, dtype=float)
        if len(s) or full_index is not None:
            s.index = pd.to_datetime(s.index)
            s = s.sort_index()
            if full_index is not None:
                s = s.reindex(full_index, fill_value=0)
            roll = s.rolling(7, min_periods=1).mean()
            color = colors_map.get(p, TEAL) if colors_map else TEAL
            ax.plot(roll.index, roll.values, color=color, linewidth=1.4)
            ax.fill_between(roll.index, roll.values, color=color, alpha=0.15)
        ax.set_title(p, fontsize=9, loc="left")
        ax.set_yticks([])
        for spine in ["top", "right", "left"]:
            ax.spines[spine].set_visible(False)
        if full_index is not None:
            ax.set_xlim(full_index[0], full_index[-1])
            ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=3, maxticks=6))
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
            ax.tick_params(axis="x", labelsize=7, rotation=0)
    for j in range(n, len(axes)):
        axes[j].axis("off")
    if full_index is not None:
        # sharex=True only links the scale — still need label_outer() to hide
        # x tick labels on every row except the bottom one, or they overlap.
        for ax in axes[:n]:
            ax.label_outer()
    fig.suptitle("Each person's activity over time (7-day rolling average, same date range for everyone)",
                 y=1.01, fontweight="bold")
    fig.tight_layout()
    _save(fig, out_path)
