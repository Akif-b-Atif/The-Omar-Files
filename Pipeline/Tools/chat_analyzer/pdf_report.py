"""
Builds the shareable PDF version of the report. Uses the same chart PNGs
as the HTML report. No dynamic explorer (not possible in a static PDF) —
noted explicitly on the cover page.
"""
import os
import re
import xml.sax.saxutils as saxutils

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak,
    HRFlowable, KeepTogether,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

import chat_config as cfg


def _pesc(s):
    """Escape text for use inside a reportlab Paragraph (which parses a
    small XML subset) — message text can contain '&', '<', '>' etc, unlike
    the old word/n-gram tokens which never could."""
    return saxutils.escape(str(s))


# --- emoji support -------------------------------------------------------
# The core PDF fonts (Helvetica etc.) have no emoji glyphs at all, so any
# emoji in message text/phrases would otherwise render as missing-glyph
# boxes or blank space. If NotoEmoji-Regular.ttf is present in the shared
# Tools/fonts/ folder (also used by pdf_export's to_pdf.py — one font
# folder for the whole Pipeline instead of a separate copy per tool), we
# register it and route just the emoji *runs* of any given text through it
# inline (reportlab Paragraphs support mixed fonts via <font name="...">),
# while everything else keeps using the surrounding style's normal font.
EMOJI_FONT_NAME = "NotoEmoji"
_FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fonts")
_EMOJI_FONT_PATH = os.path.join(_FONT_DIR, "NotoEmoji-Regular.ttf")
_EMOJI_FONT_AVAILABLE = False
if os.path.exists(_EMOJI_FONT_PATH):
    try:
        pdfmetrics.registerFont(TTFont(EMOJI_FONT_NAME, _EMOJI_FONT_PATH))
        _EMOJI_FONT_AVAILABLE = True
    except Exception:
        _EMOJI_FONT_AVAILABLE = False

_EMOJI_RUN_RE = re.compile(
    "["
    "\U0001F1E6-\U0001F1FF"   # regional indicators (flags)
    "\U0001F300-\U0001FAFF"   # misc symbols/pictographs, emoticons, supplemental symbols
    "\U00002600-\U000027BF"   # misc symbols, dingbats
    "\U00002190-\U000021FF"   # arrows
    "\U00002300-\U000023FF"   # misc technical (⌚ ⏰ ⏳ etc.)
    "\U000025A0-\U000025FF"   # geometric shapes (▪️ ◽ etc.)
    "\U00002B00-\U00002BFF"   # misc symbols and arrows
    "\U0001F000-\U0001F0FF"   # playing cards / mahjong / dominoes
    "\U0000FE0F"              # variation selector-16 (emoji presentation)
    "\U0000200D"              # zero-width joiner (emoji sequences)
    "\U000020E3"              # combining enclosing keycap (e.g. 1\uFE0F\u20E3)
    "]+",
    flags=re.UNICODE,
)


def _emoji_aware(s):
    """Escape text for a Paragraph, wrapping any emoji runs in the
    NotoEmoji font so they actually render instead of showing as tofu
    boxes. Falls back to plain escaping if NotoEmoji-Regular.ttf isn't present."""
    text = str(s)
    if not _EMOJI_FONT_AVAILABLE:
        return _pesc(text)
    pieces = []
    pos = 0
    for m in _EMOJI_RUN_RE.finditer(text):
        if m.start() > pos:
            pieces.append(_pesc(text[pos:m.start()]))
        pieces.append(f'<font face="{EMOJI_FONT_NAME}">{_pesc(m.group())}</font>')
        pos = m.end()
    if pos < len(text):
        pieces.append(_pesc(text[pos:]))
    return "".join(pieces)

TEAL = colors.HexColor("#1F6F63")
CORAL = colors.HexColor("#E4572E")
INK = colors.HexColor("#22252B")
MUTED = colors.HexColor("#7A7563")
LINE = colors.HexColor("#E9E3D3")
BG = colors.HexColor("#FAF7F0")
GOLD = colors.HexColor("#D9A441")

styles = getSampleStyleSheet()
styles.add(ParagraphStyle("ReportTitle", fontName="Helvetica-Bold", fontSize=30, leading=34,
                           textColor=INK, spaceAfter=6))
styles.add(ParagraphStyle("ReportSub", fontName="Helvetica", fontSize=12, leading=16,
                           textColor=MUTED, spaceAfter=4))
styles.add(ParagraphStyle("SectionHead", fontName="Helvetica-Bold", fontSize=17, leading=20,
                           textColor=INK, spaceBefore=18, spaceAfter=8))
styles.add(ParagraphStyle("Lede", fontName="Helvetica", fontSize=9.5, leading=13,
                           textColor=MUTED, spaceAfter=10))
styles.add(ParagraphStyle("Body9", fontName="Helvetica", fontSize=9, leading=12.5, textColor=INK))
styles.add(ParagraphStyle("Eyebrow", fontName="Helvetica-Bold", fontSize=9, leading=12,
                           textColor=TEAL, spaceAfter=2))
styles.add(ParagraphStyle("FactK", fontName="Helvetica-Bold", fontSize=8.5, textColor=MUTED))
styles.add(ParagraphStyle("FactV", fontName="Helvetica", fontSize=10.5, textColor=INK, spaceAfter=10))


def _hr(color=LINE, thickness=0.8):
    return HRFlowable(width="100%", thickness=thickness, color=color, spaceBefore=2, spaceAfter=10)


def _img(path, max_w=6.9 * inch, max_h=None):
    from PIL import Image as PILImage
    with PILImage.open(path) as im:
        w, h = im.size
    ratio = h / w
    disp_w = max_w
    disp_h = disp_w * ratio
    if max_h and disp_h > max_h:
        disp_h = max_h
        disp_w = disp_h / ratio
    return Image(path, width=disp_w, height=disp_h)


def _stat_table(rows, col_widths=None):
    """rows: list of (label, value) tuples."""
    data = [[Paragraph(f"<b>{v}</b>", styles["Body9"]), Paragraph(k, styles["FactK"])] for k, v in rows]
    t = Table(data, colWidths=col_widths or [1.1 * inch, 2.0 * inch])
    t.setStyle(TableStyle([
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, LINE),
    ]))
    return t


def _leaderboard_table(header, rows, fmt=lambda v: v):
    data = [header] + [[str(i + 1), r["person"], fmt(r["value"])] for i, r in enumerate(rows[:10])]
    t = Table(data, colWidths=[0.3 * inch, 1.7 * inch, 1.0 * inch])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, 0), (-1, 0), TEAL),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F3E9")]),
        ("GRID", (0, 0), (-1, -1), 0.5, LINE),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ALIGN", (2, 0), (2, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def _words_table(items, is_phrase=False):
    if is_phrase:
        header = [["#", "Term", "Count", "Top sayer", "First said", "Last said"]]
    else:
        header = [["#", "Term", "Count", "vs. typical chat", "Top sayer", "First said", "Last said"]]
    rows = []
    for i, it in enumerate(items[:15]):
        term = it.get("phrase") if is_phrase else it.get("word")
        row = [
            str(i + 1),
            Paragraph(_emoji_aware(term), styles["Body9"]),
            str(it["count"]),
        ]
        if not is_phrase:
            row.append(f'{it["vs_baseline"]}×')
        row.extend([
            it["top_sayer"],
            it["first_instance"]["at"][:10],
            it["last_instance"]["at"][:10],
        ])
        rows.append(row)
    col_widths = ([0.22, 1.55, 0.45, 0.75, 0.8, 0.75, 0.75] if not is_phrase
                  else [0.22, 1.8, 0.5, 0.95, 0.75, 0.75])
    t = Table(header + rows, colWidths=[w * inch for w in col_widths])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.6),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, 0), (-1, 0), INK),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F3E9")]),
        ("GRID", (0, 0), (-1, -1), 0.4, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return t


def _signature_flowables(grouped, is_phrase=False):
    """grouped is one of two shapes:
    - dict {person: [entries]} (see stats_engine._group_signature_by_person)
      — the main report / last-N-days per-person signature words/phrases,
      rendered as one small heading + table per person.
    - a flat list [entries] — an arc/mini-arc's signature words/phrases
      (this slice vs. the entire archive — see
      stats_engine.compute_arc_signature_stats), rendered as one table."""
    flowables = []
    if not grouped:
        flowables.append(Paragraph(
            "Nothing cleared the threshold for signature words/phrases yet.",
            styles["Lede"]))
        return flowables

    if isinstance(grouped, dict):
        for person, items in grouped.items():
            header = [["#", "Term", "Dominance", "Theirs / Total"]]
            rows = []
            for i, it in enumerate(items):
                term = it.get("phrase") if is_phrase else it.get("word")
                rows.append([
                    str(i + 1), Paragraph(_emoji_aware(term), styles["Body9"]),
                    f'{it["dominance_pct"]}%', f'{it["person_count"]}/{it["total_count"]}',
                ])
            t = Table(header + rows, colWidths=[0.25 * inch, 3.65 * inch, 0.95 * inch, 1.05 * inch])
            t.setStyle(TableStyle([
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7.6),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("BACKGROUND", (0, 0), (-1, 0), CORAL),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F3E9")]),
                ("GRID", (0, 0), (-1, -1), 0.4, LINE),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]))
            flowables.append(KeepTogether([Paragraph(_emoji_aware(person), styles["Eyebrow"]), t, Spacer(1, 10)]))
        return flowables

    header = [["#", "Term", "vs. archive", "Here / archive-wide", "Top sayer here"]]
    rows = []
    for i, it in enumerate(grouped):
        term = it.get("phrase") if is_phrase else it.get("word")
        rows.append([
            str(i + 1), Paragraph(_emoji_aware(term), styles["Body9"]),
            f'{it["vs_archive"]}×', f'{it["count_in_arc"]}/{it["count_in_archive"]}',
            it["top_sayer"],
        ])
    t = Table(header + rows, colWidths=[0.25 * inch, 2.5 * inch, 0.85 * inch, 1.05 * inch, 1.0 * inch])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.6),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, 0), (-1, 0), CORAL),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F3E9")]),
        ("GRID", (0, 0), (-1, -1), 0.4, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    flowables.append(t)
    return flowables


def _top3_fact(title, items, fmt):
    """One 'fun fact' entry rendered as a top-3 (or fewer) ranked list."""
    if not items:
        body = "—"
    else:
        body = "<br/>".join(f"{i + 1}. {_emoji_aware(fmt(it))}" for i, it in enumerate(items))
    return [Paragraph(title, styles["FactK"]), Paragraph(body, styles["FactV"])]


def _cover_flowables(overall, participants, title_suffix=""):
    flow = []
    flow.append(Spacer(1, 0.4 * inch))
    flow.append(Paragraph(f"GROUP CHAT REPORT{title_suffix}", styles["Eyebrow"]))
    flow.append(Paragraph(f"{overall['total_messages']:,} messages, {len(participants)} people,"
                           f" {overall['total_days_spanned']:,} days.", styles["ReportTitle"]))
    flow.append(Paragraph(f"{overall['first_message_ts'][:10]} → {overall['last_message_ts'][:10]}",
                           styles["ReportSub"]))
    flow.append(Spacer(1, 0.15 * inch))
    flow.append(_hr(TEAL, 1.4))

    overview_rows = [
        (f'{overall["total_messages"]:,}', "Total messages"),
        (f'{overall["avg_messages_per_day"]}', "Avg messages / day"),
        (f'{overall["pct_days_active"]}%', "Days with activity"),
        (f'{overall["total_words_sent"]:,}', "Words sent"),
        (f'{overall["total_media"]:,}', "Media shared"),
        (f'{overall["median_reply_gap_minutes"]} min', "Median reply gap"),
    ]
    cw = [0.95 * inch, 1.35 * inch]
    grid = Table([[_stat_table(overview_rows[0:2], cw), _stat_table(overview_rows[2:4], cw), _stat_table(overview_rows[4:6], cw)]],
                 colWidths=[2.35 * inch] * 3)
    grid.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    flow.append(grid)
    return flow


def _overview_block(overall, chart_paths):
    flow = [Spacer(1, 0.25 * inch), _img(chart_paths["per_day"]), PageBreak()]
    return flow


def _timing_block(chart_paths):
    return [
        Paragraph("When the chat comes alive", styles["SectionHead"]), _hr(),
        _img(chart_paths["by_hour"], max_h=2.6 * inch), Spacer(1, 8),
        _img(chart_paths["by_weekday"], max_h=2.6 * inch), PageBreak(),
        _img(chart_paths["heatmap"], max_h=3.0 * inch), Spacer(1, 10),
        _img(chart_paths["by_month"], max_h=2.8 * inch), PageBreak(),
    ]


def _leaderboards_block(lb, chart_paths, individual_stats):
    flow = [Paragraph("Who does what the most", styles["SectionHead"]), _hr()]
    lb_defs = [
        ("most_messages", "Most messages", lambda v: f"{v:,}"),
        ("biggest_vocab", "Biggest vocabulary", lambda v: f"{v:,}"),
        ("most_swears_rate", "Curses most /100 msgs", lambda v: v),
        ("most_laughs_rate", "Laughs most /100 msgs", lambda v: v),
        ("most_questions", "Most questions asked", lambda v: v),
        ("most_mentions_given", "Tags others most", lambda v: v),
        ("most_mentions_received", "Gets tagged most", lambda v: v),
        ("most_night_owl", "Biggest night owl", lambda v: f"{v}%"),
        ("most_conversation_starts", "Revives chat most", lambda v: v),
        ("most_double_texting", "Double-texts most", lambda v: f"{v}%"),
    ]
    cells = []
    for key, title, fmt in lb_defs:
        block = [Paragraph(f"<b>{title}</b>", styles["Body9"]), Spacer(1, 3),
                 _leaderboard_table(["#", "Person", "Value"], lb[key], fmt)]
        cells.append(block)
    rows_of_two = [cells[i:i + 2] for i in range(0, len(cells), 2)]
    for pair in rows_of_two:
        if len(pair) == 1:
            pair.append([Spacer(1, 1)])
        t = Table([pair], colWidths=[3.4 * inch, 3.4 * inch])
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
        flow.append(t)
        flow.append(Spacer(1, 10))
    flow.append(PageBreak())

    flow.append(Paragraph("Message volume by person", styles["SectionHead"]))
    flow.append(_hr())
    flow.append(_img(chart_paths["most_msgs"], max_h=4.5 * inch))
    flow.append(PageBreak())
    return flow


def _individuals_block(chart_paths, individual_stats):
    flow = [
        Paragraph("Everyone's activity fingerprint — hourly rhythm", styles["SectionHead"]), _hr(),
        _img(chart_paths["hourly_sm"], max_h=7.2 * inch), PageBreak(),
        Paragraph("Everyone's activity fingerprint — over time", styles["SectionHead"]), _hr(),
        _img(chart_paths["timeline_sm"], max_h=7.2 * inch), PageBreak(),
    ]

    flow.append(Paragraph("Full per-person stat table", styles["SectionHead"]))
    flow.append(_hr())
    header = [["Person", "Msgs", "Vocab", "Avg words", "Swears/100", "Laughs/100", "Qs", "Tags g/r", "Night owl"]]
    rows = []
    for p, s in sorted(individual_stats.items(), key=lambda x: -x[1]["total_messages"]):
        rows.append([p, f'{s["total_messages"]:,}', s["unique_words"], s["avg_words_per_message"],
                     s["swear_rate_per_100"], s["laugh_rate_per_100"], s["question_count"],
                     f'{s["mentions_given"]}/{s["mentions_received"]}', f'{s["night_owl_pct"]}%'])
    t = Table(header + rows, colWidths=[0.95 * inch, 0.55 * inch, 0.55 * inch, 0.65 * inch,
                                         0.7 * inch, 0.7 * inch, 0.4 * inch, 0.7 * inch, 0.65 * inch])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, 0), (-1, 0), INK),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F3E9")]),
        ("GRID", (0, 0), (-1, -1), 0.4, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    flow.append(t)
    flow.append(PageBreak())
    return flow


def _words_block(wordstats, phrasestats, cfg_profile=cfg):
    """cfg_profile: the (possibly overridden) namespace these stats were
    actually computed with — used only so the descriptive Lede text quotes
    the right thresholds (e.g. for the "last N days" section, which uses
    looser LAST_PERIOD_* thresholds)."""
    is_arc_signature = not isinstance(wordstats["signature_words"], dict)
    if is_arc_signature:
        sig_words_lede = ("This arc/mini-arc's own top words, compared against how often the entire "
                           "archive uses them — what this slice of time talked about noticeably more "
                           "than the chat does normally.")
        sig_phrases_lede = "Same idea, but for whole repeated messages."
    else:
        sig_words_lede = (f"Each member with {cfg_profile.SIGNATURE_MIN_MESSAGES}+ total messages gets "
                           f"their own top {cfg_profile.SIGNATURE_TOP_N_PER_PERSON} words — the ones "
                           f"they personally dominate the use of.")
        sig_phrases_lede = (f"Same idea as signature words, per member with "
                             f"{cfg_profile.SIGNATURE_MIN_MESSAGES}+ messages, but for whole repeated "
                             f"messages.")

    flow = [
        Paragraph("Most repeated words", styles["SectionHead"]),
        Paragraph(
            f"Words with {cfg_profile.MIN_WORD_LENGTH}+ letters, said at least {cfg_profile.MIN_REPEAT_COUNT} times "
            f"— common pronouns/verbs/fillers/names are filtered out, and words are ranked by how much MORE "
            f"often this chat says them than a synthetic, generic group chat does (\"vs. typical chat\"), not "
            f"just by raw count, so this surfaces this chat's actual topics instead of universal filler.",
            styles["Lede"]),
        _words_table(wordstats["top_words"]), PageBreak(),

        Paragraph("Signature words", styles["SectionHead"]),
        Paragraph(sig_words_lede, styles["Lede"]),
    ]
    flow.extend(_signature_flowables(wordstats["signature_words"]))
    flow.append(PageBreak())

    flow.append(Paragraph("Most repeated phrases", styles["SectionHead"]))
    flow.append(Paragraph(
        f"A \"phrase\" here is a whole message ({cfg_profile.MIN_PHRASE_LENGTH}+ letters) — two messages "
        f"count as the same phrase if they're identical once emojis, punctuation, and capitalization "
        f"are ignored, said at least {cfg_profile.MIN_REPEAT_COUNT} times.",
        styles["Lede"]))
    flow.append(_words_table(phrasestats["top_phrases"], is_phrase=True))
    flow.append(PageBreak())

    flow.append(Paragraph("Signature phrases", styles["SectionHead"]))
    flow.append(Paragraph(sig_phrases_lede, styles["Lede"]))
    flow.extend(_signature_flowables(phrasestats["signature_phrases"], is_phrase=True))
    flow.append(PageBreak())
    return flow


def _mentions_block(chart_paths):
    return [
        Paragraph("Who tags whom", styles["SectionHead"]), _hr(),
        _img(chart_paths["mentions"], max_h=4.2 * inch), PageBreak(),
    ]


def _funfacts_block(overall, chart_paths):
    flow = [Paragraph("Fun facts", styles["SectionHead"]),
            Paragraph("Top 3 in each category.", styles["Lede"]), _hr()]

    fact_blocks = [
        _top3_fact("BUSIEST DAYS EVER", overall["top3_busiest_days"],
                   lambda it: f'{it["date"]} — {it["count"]} messages'),
        _top3_fact("QUIETEST ACTIVE DAYS", overall["top3_quietest_active_days"],
                   lambda it: f'{it["date"]} — {it["count"]} message(s)'),
        _top3_fact("LONGEST SILENCES", overall["top3_longest_silences"],
                   lambda it: f'{it["hours"]} hours ({it["from"][:16].replace("T"," ")} → {it["to"][:16].replace("T"," ")})'),
        _top3_fact("LONGEST ACTIVE STREAKS", overall["top3_longest_active_streaks"],
                   lambda it: f'{it["days"]} days straight ({it["start"]} → {it["end"]})'),
        _top3_fact("LONGEST MESSAGES EVER", overall["top3_longest_messages"],
                   lambda it: f'{it["person"]} — {it["words"]} words ({it["date"][:10]})'),
        _top3_fact("MOST MEDIA-HEAVY DAYS", overall["top3_media_heavy_days"],
                   lambda it: f'{it["date"]} — {it["count"]} media items'),
    ]
    for block in fact_blocks:
        flow.extend(block)
    flow.append(Spacer(1, 4))
    flow.append(Paragraph("TOTAL MEDIA / DELETED / EDITED", styles["FactK"]))
    flow.append(Paragraph(
        f'{overall["total_media"]:,} media shared · {overall["total_deleted"]:,} deleted · '
        f'{overall["total_edited"]:,} edited', styles["FactV"]))
    flow.append(Spacer(1, 14))
    flow.append(_img(chart_paths["media"], max_h=2.8 * inch))
    return flow


SECTION_ORDER = ["overview", "timing", "leaderboards", "individuals", "words", "mentions", "funfacts"]
SECTION_TITLES = {
    "overview": "Overview", "timing": "Timing", "leaderboards": "Leaderboards",
    "individuals": "Individuals", "words": "Words & phrases", "mentions": "Mentions",
    "funfacts": "Fun facts",
}


def _section_blocks(overall, individual_stats, lb, wordstats, phrasestats, chart_paths, cfg_profile=cfg):
    """Maps each section name to a zero-arg callable returning its
    flowables, bound to the given data. Shared between the main report and
    the "last N days" part so both use identical rendering logic."""
    return {
        "overview": lambda: _overview_block(overall, chart_paths),
        "timing": lambda: _timing_block(chart_paths),
        "leaderboards": lambda: _leaderboards_block(lb, chart_paths, individual_stats),
        "individuals": lambda: _individuals_block(chart_paths, individual_stats),
        "words": lambda: _words_block(wordstats, phrasestats, cfg_profile),
        "mentions": lambda: _mentions_block(chart_paths),
        "funfacts": lambda: _funfacts_block(overall, chart_paths),
    }


def build_pdf(overall, individual_stats, lb, wordstats, phrasestats, mention_pairs,
              chart_paths, participants, out_path, sections=None, last_period=None,
              arc_periods=None, cfg_profile=cfg):
    """sections: optional iterable restricting which of SECTION_ORDER (plus
    "lastperiod" and "arcs") get rendered — defaults to everything.
    last_period: optional dict {"days", "bundle", "charts", "cfg"} — pass
    None (or omit "lastperiod" from `sections`) to skip that part of the
    PDF entirely. arc_periods: optional list of dicts, one per arc/
    mini-arc — see load_arc_segments()/the "arcs" block in
    analyze_chat.py's main() — pass None/empty (or omit "arcs" from
    `sections`) to skip that part entirely. cfg_profile: the (possibly
    CLI-overridden) namespace wordstats/phrasestats were actually computed
    with, so the descriptive text in the words section quotes the right
    thresholds."""
    sections = set(s.lower() for s in sections) if sections is not None else set(SECTION_ORDER) | {"lastperiod", "arcs"}
    active = [s for s in SECTION_ORDER if s in sections]
    show_lastperiod = "lastperiod" in sections and last_period and last_period.get("bundle")
    show_arcs = "arcs" in sections and bool(arc_periods)

    doc = SimpleDocTemplate(out_path, pagesize=letter,
                             topMargin=0.6 * inch, bottomMargin=0.6 * inch,
                             leftMargin=0.55 * inch, rightMargin=0.55 * inch)
    story = []

    # ---- cover ----
    story.extend(_cover_flowables(overall, participants))
    blocks = _section_blocks(overall, individual_stats, lb, wordstats, phrasestats, chart_paths,
                              cfg_profile=cfg_profile)
    for s in active:
        story.extend(blocks[s]())

    # ---- last N days part ----
    if show_lastperiod:
        days = last_period["days"]
        lp = last_period["bundle"]
        lp_cfg = last_period.get("cfg", cfg)
        story.append(Paragraph(f"PART TWO — LAST {days} DAYS", styles["ReportTitle"]))
        story.append(Paragraph(
            f"Same analysis, restricted to {lp['overall']['first_message_ts'][:10]} → "
            f"{lp['overall']['last_message_ts'][:10]} ({lp['overall']['total_messages']:,} messages). "
            f"Looser noise thresholds are used throughout this part since it's a much smaller slice "
            f"than the full archive — see LAST_PERIOD_* in chat_config.py.",
            styles["ReportSub"]))
        story.append(Spacer(1, 0.15 * inch))
        story.append(_hr(CORAL, 1.4))
        story.append(PageBreak())
        lp_blocks = _section_blocks(lp["overall"], lp["individual_stats"], lp["lb"],
                                     lp["wordstats"], lp["phrasestats"], last_period["charts"],
                                     cfg_profile=lp_cfg)
        # every section shown for the last-period part, regardless of which
        # top-level `sections` were chosen for the main report — it's a
        # compact self-contained recap
        for s in SECTION_ORDER:
            story.extend(lp_blocks[s]())

    # ---- arcs & mini-arcs part ----
    if show_arcs:
        story.append(Paragraph("PART THREE — ARCS & MINI-ARCS" if show_lastperiod else "PART TWO — ARCS & MINI-ARCS",
                                styles["ReportTitle"]))
        story.append(Paragraph(
            f"The same analysis again, run separately for each of the {len(arc_periods)} high-activity "
            f"period(s) arc_analyzer.py found in arc_report.txt. Names and descriptions come from that "
            f"file's \"ARC NAMES\" table — edit them there and re-run to update this PDF. Uses the same "
            f"looser noise thresholds as the last-N-days part above, since each of these is also a much "
            f"smaller slice than the full archive. Each arc/mini-arc's signature words/phrases compare "
            f"that slice against the ENTIRE archive (not a per-person breakdown), surfacing what that "
            f"stretch of time talked about noticeably more than the chat does normally.",
            styles["ReportSub"]))
        story.append(Spacer(1, 0.15 * inch))
        story.append(_hr(CORAL, 1.4))
        story.append(PageBreak())
        for i, period in enumerate(arc_periods, start=1):
            arc = period["bundle"]
            arc_cfg = period.get("cfg", cfg)
            kind = "Arc" if period["seg_type"] == "arc" else "Mini-arc"
            story.extend(_cover_flowables(arc["overall"], arc["participants"],
                                           title_suffix=f" — {kind.upper()} {i}: {period['name'].upper()}"))
            if period.get("description"):
                story.append(Spacer(1, 0.05 * inch))
                story.append(Paragraph(period["description"], styles["Lede"]))
            arc_blocks = _section_blocks(arc["overall"], arc["individual_stats"], arc["lb"],
                                          arc["wordstats"], arc["phrasestats"], period["charts"],
                                          cfg_profile=arc_cfg)
            for s in SECTION_ORDER:
                story.extend(arc_blocks[s]())
            if i < len(arc_periods):
                story.append(PageBreak())

    story.append(Spacer(1, 20))
    story.append(_hr())
    story.append(Paragraph(
        "Want to search individual words/phrases, filter by date range, or compare two people "
        "interactively? Open the HTML version of this report (chat_report.html) in a browser — "
        "those tools only work there, not in this PDF.", styles["Lede"]))

    doc.build(story)
    return out_path
