"""
Builds the single-file HTML report (charts embedded as base64 so the HTML
itself is fully self-contained), plus the dynamic explorer section that
fetches chat_search_data.json at view-time.
"""
import base64
import html as htmlmod

import chat_config as cfg


def img_b64(path):
    with open(path, "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode("ascii")


def esc(s):
    return htmlmod.escape(str(s), quote=True)


CSS = """
:root{
  --bg:#FAF7F0; --ink:#22252B; --muted:#7A7563; --card:#FFFFFF;
  --line:#E9E3D3; --teal:#1F6F63; --coral:#E4572E; --gold:#D9A441;
  --blue:#3E6C9E; --plum:#7A5C7E;
  --mono: ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", Menlo, monospace;
  --serif: Georgia, "Iowan Old Style", "Palatino Linotype", serif;
  --sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}
*{box-sizing:border-box}
body{margin:0; background:var(--bg); color:var(--ink); font-family:var(--sans); line-height:1.5;}
.wrap{max-width:1180px; margin:0 auto; padding:0 24px;}
a{color:var(--teal)}

.hero{padding:64px 0 40px; border-bottom:1px solid var(--line);}
.hero .eyebrow{font-family:var(--mono); letter-spacing:.14em; text-transform:uppercase;
  font-size:12px; color:var(--muted); margin-bottom:14px;}
.hero h1{font-family:var(--serif); font-size:44px; margin:0 0 10px; letter-spacing:-0.01em;}
.hero p.sub{color:var(--muted); font-size:16px; max-width:640px; margin:0 0 22px;}
.hero .stamp{display:inline-flex; gap:10px; align-items:center; font-family:var(--mono);
  font-size:13px; background:var(--card); border:1px solid var(--line); border-radius:999px;
  padding:8px 16px; color:var(--muted);}

nav.tabs{position:sticky; top:0; background:rgba(250,247,240,.92); backdrop-filter:blur(6px);
  border-bottom:1px solid var(--line); z-index:50; overflow-x:auto; white-space:nowrap;}
nav.tabs .wrap{padding:0 24px;}
nav.tabs a{display:inline-block; padding:14px 16px; font-size:13px; font-weight:600;
  color:var(--muted); text-decoration:none; border-bottom:2px solid transparent;}
nav.tabs a:hover{color:var(--ink); border-color:var(--gold);}

.divider{display:inline-flex; align-items:center; gap:10px; margin:56px 0 22px;
  font-family:var(--mono); font-size:12px; letter-spacing:.1em; text-transform:uppercase;
  color:var(--muted); background:var(--card); border:1px solid var(--line);
  padding:7px 16px; border-radius:999px;}
section{scroll-margin-top:56px;}
section h2{font-family:var(--serif); font-size:26px; margin:0 0 6px;}
section p.lede{color:var(--muted); margin:0 0 22px; max-width:760px; font-size:14.5px;}

.grid{display:grid; gap:16px;}
.grid-4{grid-template-columns:repeat(4,1fr);}
.grid-3{grid-template-columns:repeat(3,1fr);}
.grid-2{grid-template-columns:repeat(2,1fr);}
@media(max-width:900px){.grid-4{grid-template-columns:repeat(2,1fr);} .grid-3{grid-template-columns:repeat(2,1fr);} .grid-2{grid-template-columns:1fr;}}

.card{background:var(--card); border:1px solid var(--line); border-radius:14px; padding:20px;}
.stat .num{font-family:var(--mono); font-size:28px; font-weight:700; color:var(--teal);}
.stat .lbl{font-size:12.5px; color:var(--muted); margin-top:4px;}
.stat .sub{font-size:11.5px; color:var(--muted); margin-top:2px; font-family:var(--mono);}

.chart-card{background:var(--card); border:1px solid var(--line); border-radius:14px;
  padding:14px; margin-bottom:18px;}
.chart-card img{width:100%; display:block; border-radius:6px;}

table{width:100%; border-collapse:collapse; font-size:13.5px;}
table th{text-align:left; font-family:var(--mono); font-size:11px; text-transform:uppercase;
  letter-spacing:.06em; color:var(--muted); border-bottom:1px solid var(--line); padding:8px 10px;}
table td{padding:9px 10px; border-bottom:1px solid var(--line); vertical-align:top;}
table tr:hover td{background:#FBF4E8;}
.badge{display:inline-block; padding:2px 9px; border-radius:999px; background:#EEF3F0;
  color:var(--teal); font-family:var(--mono); font-size:11px;}
.pill-count{font-family:var(--mono); font-weight:700; color:var(--coral);}

.fact{border-left:3px solid var(--gold); padding:4px 0 4px 16px; margin-bottom:18px;}
.fact .k{font-family:var(--mono); font-size:11px; text-transform:uppercase; color:var(--muted); letter-spacing:.06em;}
.fact .v{font-size:15.5px; margin-top:4px;}

.explorer input, .explorer select, .explorer button{
  font-family:var(--sans); font-size:14px; padding:10px 12px; border-radius:8px;
  border:1px solid var(--line); background:#fff; color:var(--ink);}
.explorer button{background:var(--ink); color:#fff; border-color:var(--ink); cursor:pointer; font-weight:600;}
.explorer button:hover{background:var(--teal); border-color:var(--teal);}
.explorer .row{display:flex; gap:10px; flex-wrap:wrap; align-items:center; margin-bottom:16px;}
.bar-row{display:flex; align-items:center; gap:10px; margin-bottom:6px; font-size:13px;}
.bar-row .name{width:110px; flex:0 0 auto; color:var(--muted); font-size:12.5px;}
.bar-row .track{flex:1; background:#EFEAE0; border-radius:5px; height:14px; overflow:hidden;}
.bar-row .fill{height:100%; background:var(--teal); border-radius:5px;}
.bar-row .val{width:54px; text-align:right; font-family:var(--mono); font-size:12px; color:var(--muted);}
.notice{background:#FDF3E7; border:1px solid #EFD9B0; border-radius:10px; padding:12px 16px;
  font-size:13px; color:#7A5A15; margin-bottom:18px;}
.snippet{font-family:var(--mono); font-size:12.5px; background:#F5F1E6; border-radius:6px;
  padding:8px 10px; margin-top:6px; color:#555;}

footer{padding:50px 0 80px; color:var(--muted); font-size:12.5px; text-align:center;}
"""


def stat_card(num, lbl, sub=""):
    sub_html = f'<div class="sub">{esc(sub)}</div>' if sub else ""
    return f'<div class="card stat"><div class="num">{esc(num)}</div><div class="lbl">{esc(lbl)}</div>{sub_html}</div>'


def divider(label):
    return f'<div class="divider">● {esc(label)}</div>'


def chart_card(b64, alt):
    return f'<div class="chart-card"><img src="{b64}" alt="{esc(alt)}"></div>'


def render_overview(overall):
    cards = [
        stat_card(f'{overall["total_messages"]:,}', "Total messages"),
        stat_card(overall["total_days_spanned"], "Days spanned", f'{overall["first_message_ts"][:10]} → {overall["last_message_ts"][:10]}'),
        stat_card(overall["avg_messages_per_day"], "Avg messages / day"),
        stat_card(f'{overall["pct_days_active"]}%', "Days with ≥1 message", f'{overall["active_days"]} active / {overall["silent_days"]} silent'),
        stat_card(f'{overall["total_words_sent"]:,}', "Words sent"),
        stat_card(overall["avg_words_per_message"], "Avg words / message"),
        stat_card(overall["total_media"], "Media shared"),
        stat_card(f'{overall["median_reply_gap_minutes"]} min', "Median gap between messages"),
    ]
    return f"""
<section id="overview">
  {divider("Overview")}
  <h2>The whole archive, at a glance</h2>
  <p class="lede">Every number below is computed straight from Full_Archive.txt — no sampling.</p>
  <div class="grid grid-4">{''.join(cards)}</div>
</section>
"""


def render_timing(charts):
    return f"""
<section id="timing">
  {divider("Timing")}
  <h2>When the group chat comes alive</h2>
  <p class="lede">Daily volume, and the weekly/hourly rhythm the group falls into.</p>
  {chart_card(charts['per_day'], 'Messages per day')}
  <div class="grid grid-2">
    {chart_card(charts['by_hour'], 'Messages by hour')}
    {chart_card(charts['by_weekday'], 'Messages by weekday')}
  </div>
  {chart_card(charts['heatmap'], 'Weekday x hour heatmap')}
  {chart_card(charts['by_month'], 'Messages by month')}
</section>
"""


def render_leaderboards(lb, charts, individual_stats):
    def top_row(rows, fmt=lambda v: v):
        rows = rows[:5]
        out = []
        maxv = max((r["value"] for r in rows), default=1) or 1
        for r in rows:
            pct = 100 * r["value"] / maxv
            out.append(
                f'<div class="bar-row"><div class="name">{esc(r["person"])}</div>'
                f'<div class="track"><div class="fill" style="width:{pct:.1f}%"></div></div>'
                f'<div class="val">{esc(fmt(r["value"]))}</div></div>'
            )
        return "".join(out)

    leaderboard_defs = [
        ("most_messages", "Most messages sent", ""),
        ("biggest_vocab", "Biggest vocabulary (unique words)", ""),
        ("most_swears_rate", "Curses most (per 100 msgs)", ""),
        ("most_laughs_rate", "Laughs most (per 100 msgs)", ""),
        ("most_questions", "Asks the most questions", ""),
        ("most_mentions_given", "Tags others the most", ""),
        ("most_mentions_received", "Gets tagged the most", ""),
        ("most_night_owl", "Biggest night owl (% sent 12–5am)", "%"),
        ("most_early_bird", "Biggest early bird (% sent 5–9am)", "%"),
        ("most_double_texting", "Double-texts the most (%)", "%"),
        ("most_conversation_starts", "Revives the chat most often", ""),
        ("longest_avg_messages", "Writes the longest messages (avg words)", ""),
        ("most_media", "Sends the most media", ""),
        ("most_edited", "Edits messages most often", ""),
    ]
    cards = []
    for key, title, suffix in leaderboard_defs:
        fmt = (lambda v, s=suffix: f"{v}{s}")
        cards.append(f'<div class="card"><h3 style="margin-top:0;font-size:14.5px">{esc(title)}</h3>{top_row(lb[key], fmt)}</div>')

    return f"""
<section id="leaderboards">
  {divider("Leaderboards")}
  <h2>Who does what the most</h2>
  <p class="lede">Top 5 shown per category — full per-person numbers are in the Individuals section below.</p>
  <div class="grid grid-3">{''.join(cards)}</div>
  <div style="margin-top:18px">{chart_card(charts['most_msgs'], 'Most messages')}</div>
  <div class="grid grid-2">
    {chart_card(charts['vocab'], 'Biggest vocab')}
    {chart_card(charts['mentions'], 'Mentions given vs received')}
  </div>
</section>
"""


def render_individuals(charts, individual_stats, colors):
    rows = []
    for p, s in sorted(individual_stats.items(), key=lambda x: -x[1]["total_messages"]):
        color = colors.get(p, "#1F6F63")
        top_emoji = " ".join(f'{e["emoji"]}×{e["count"]}' for e in s["top_emojis"][:3]) or "—"
        rows.append(f"""
        <tr>
          <td><span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:{color};margin-right:8px"></span><b>{esc(p)}</b></td>
          <td>{s['total_messages']:,}<br><span class="badge">{s['pct_of_all_messages']}%</span></td>
          <td>{s['unique_words']:,}</td>
          <td>{s['avg_words_per_message']}</td>
          <td>{s['swear_rate_per_100']}/100</td>
          <td>{s['laugh_rate_per_100']}/100</td>
          <td>{s['question_count']}</td>
          <td>{s['mentions_given']} / {s['mentions_received']}</td>
          <td>{s['night_owl_pct']}%</td>
          <td>{s['double_text_rate_pct']}%</td>
          <td>{s['conversation_starts']}</td>
          <td>{top_emoji}</td>
        </tr>""")

    return f"""
<section id="individuals">
  {divider("Individuals")}
  <h2>Everyone's fingerprint</h2>
  <p class="lede">Hourly rhythm and activity-over-time, per person, plus the full stat table.</p>
  {chart_card(charts['hourly_sm'], "Hourly fingerprints")}
  {chart_card(charts['timeline_sm'], "Activity over time")}
  <div class="card" style="overflow-x:auto">
  <table>
    <thead><tr>
      <th>Person</th><th>Messages</th><th>Vocab</th><th>Avg words/msg</th>
      <th>Swears</th><th>Laughs</th><th>Questions</th><th>Tags given/received</th>
      <th>Night owl</th><th>Double-texts</th><th>Chat starts</th><th>Top emoji</th>
    </tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
  </div>
</section>
"""


def render_words_phrases(wordstats, phrasestats, cfg_profile=cfg):
    """cfg_profile: the (possibly overridden) namespace these stats were
    actually computed with, so the descriptive text quotes the right
    thresholds — e.g. the "last N days" section uses looser LAST_PERIOD_*
    thresholds than the main report."""
    def word_rows(items, is_phrase=False):
        out = []
        for it in items:
            term = it.get("phrase") if is_phrase else it.get("word")
            vs_col = "" if is_phrase else f'<td class="pill-count">{it["vs_baseline"]}×</td>'
            out.append(f"""
            <tr>
              <td><b>{esc(term)}</b></td>
              <td class="pill-count">{it['count']}</td>
              {vs_col}
              <td>{esc(it['top_sayer'])} <span class="badge">{it['top_sayer_count']}×</span></td>
              <td>{esc(it['first_instance']['by'])}<br><span class="badge">{it['first_instance']['at'][:10]}</span></td>
              <td>{esc(it['last_instance']['by'])}<br><span class="badge">{it['last_instance']['at'][:10]}</span></td>
            </tr>""")
        return "".join(out)

    def signature_person_cards(grouped, is_phrase=False):
        """grouped is one of two shapes:
        - dict {person: [entries]} — the main report / last-N-days
          per-person signature words/phrases (their own top words, the
          ones they personally dominate the use of), rendered as one card
          per person.
        - a flat list [entries] — an arc/mini-arc's signature words/
          phrases (this slice's own words/phrases vs. the entire
          archive), rendered as a single table since it isn't per-person."""
        if not grouped:
            return '<p class="lede">Nothing cleared the threshold yet.</p>'

        if isinstance(grouped, dict):
            cards = []
            for person, items in grouped.items():
                rows = []
                for it in items:
                    term = it.get("phrase") if is_phrase else it.get("word")
                    rows.append(f"""
                    <tr>
                      <td><b>{esc(term)}</b></td>
                      <td class="pill-count">{it['dominance_pct']}%</td>
                      <td>{it['person_count']} / {it['total_count']}</td>
                    </tr>""")
                cards.append(f"""
                <div class="card">
                  <h4 style="margin:0 0 10px">{esc(person)}</h4>
                  <table><thead><tr><th>{'Phrase' if is_phrase else 'Word'}</th><th>Dominance</th><th>Theirs / Total</th></tr></thead>
                  <tbody>{''.join(rows)}</tbody></table>
                </div>""")
            return f'<div class="grid grid-3">{"".join(cards)}</div>'

        rows = []
        for it in grouped:
            term = it.get("phrase") if is_phrase else it.get("word")
            rows.append(f"""
            <tr>
              <td><b>{esc(term)}</b></td>
              <td class="pill-count">{it['vs_archive']}×</td>
              <td>{it['count_in_arc']} here / {it['count_in_archive']} archive-wide</td>
              <td>{esc(it['top_sayer'])} <span class="badge">{it['top_sayer_count']}×</span></td>
            </tr>""")
        return f"""<table><thead><tr><th>{'Phrase' if is_phrase else 'Word'}</th>
          <th>vs. rest of archive</th><th>Said here / archive-wide</th><th>Top sayer here</th></tr></thead>
          <tbody>{''.join(rows)}</tbody></table>"""

    is_arc_signature = not isinstance(wordstats["signature_words"], dict)
    if is_arc_signature:
        sig_words_lede = ("This arc/mini-arc's own top words, compared against how often the entire "
                           "archive uses them — i.e. what this specific slice of time talked about "
                           "noticeably more than the chat does normally.")
        sig_phrases_lede = "Same idea, but for whole repeated messages."
    else:
        sig_words_lede = (f"Each member with {cfg_profile.SIGNATURE_MIN_MESSAGES}+ total "
                           f"messages, and their own top {cfg_profile.SIGNATURE_TOP_N_PER_PERSON} words — "
                           f"the ones they personally dominate the use of.")
        sig_phrases_lede = "Same idea, per member, but for whole repeated messages."

    return f"""
<section id="words">
  {divider("Words & Phrases")}
  <h2>What gets said, and by whom</h2>
  <p class="lede">Top {len(wordstats['top_words'])} words ({cfg_profile.MIN_WORD_LENGTH}+ letters, common
  pronouns/verbs/fillers/names filtered out) and phrases ({cfg_profile.MIN_PHRASE_LENGTH}+ letters — a
  "phrase" is a whole message; two messages count as the same phrase if they're identical once emojis,
  punctuation, and capitalization are ignored), each said at least {cfg_profile.MIN_REPEAT_COUNT} times.
  Words are ranked by how much MORE often this chat says them than a synthetic, generic group chat does
  (the "vs. typical chat" column) — not just by raw count — so this surfaces this chat's actual topics
  instead of universal chat filler.</p>

  <div class="grid grid-2">
    <div class="card">
      <h3 style="margin-top:0">Most repeated words</h3>
      <table><thead><tr><th>Word</th><th>Total</th><th>vs. typical chat</th><th>Top sayer</th><th>First said</th><th>Last said</th></tr></thead>
      <tbody>{word_rows(wordstats['top_words'])}</tbody></table>
    </div>
    <div class="card">
      <h3 style="margin-top:0">Most repeated phrases</h3>
      <table><thead><tr><th>Phrase</th><th>Total</th><th>Top sayer</th><th>First said</th><th>Last said</th></tr></thead>
      <tbody>{word_rows(phrasestats['top_phrases'], True)}</tbody></table>
    </div>
  </div>

  <h3 style="margin:28px 0 4px">Signature words</h3>
  <p class="lede" style="margin-bottom:14px">{sig_words_lede}</p>
  {signature_person_cards(wordstats['signature_words'])}

  <h3 style="margin:28px 0 4px">Signature phrases</h3>
  <p class="lede" style="margin-bottom:14px">{sig_phrases_lede}</p>
  {signature_person_cards(phrasestats['signature_phrases'], True)}
</section>
"""


def render_mentions(pairs, charts):
    rows = "".join(
        f'<tr><td>{esc(p["from"])} → {esc(p["to"])}</td><td class="pill-count">{p["count"]}</td></tr>'
        for p in pairs[:15]
    )
    return f"""
<section id="mentions">
  {divider("Mentions")}
  <h2>Who tags whom</h2>
  <div class="grid grid-2">
    {chart_card(charts['mentions'], 'Mentions given vs received')}
    <div class="card">
      <h3 style="margin-top:0">Top tagging pairs</h3>
      <table><thead><tr><th>Pair</th><th>Times</th></tr></thead><tbody>{rows}</tbody></table>
    </div>
  </div>
</section>
"""


def render_funfacts(overall, charts):
    def top3(title, items, fmt):
        if not items:
            body = "—"
        else:
            body = "".join(f'<div>{i + 1}. {fmt(it)}</div>' for i, it in enumerate(items))
        return f'<div class="fact"><div class="k">{esc(title)}</div><div class="v">{body}</div></div>'

    top3_facts = [
        top3("Busiest days ever", overall["top3_busiest_days"],
             lambda it: f'{esc(it["date"])} — {it["count"]} messages'),
        top3("Quietest active days", overall["top3_quietest_active_days"],
             lambda it: f'{esc(it["date"])} — {it["count"]} message(s)'),
        top3("Longest silences", overall["top3_longest_silences"],
             lambda it: f'{it["hours"]} hours, from {esc(it["from"][:16].replace("T"," "))} to {esc(it["to"][:16].replace("T"," "))}'),
        top3("Longest active streaks", overall["top3_longest_active_streaks"],
             lambda it: f'{it["days"]} days straight ({esc(it["start"])} → {esc(it["end"])})'),
        top3("Longest messages ever", overall["top3_longest_messages"],
             lambda it: f'{esc(it["person"])} — {it["words"]} words ({esc(it["date"][:10])})'),
        top3("Most media-heavy days", overall["top3_media_heavy_days"],
             lambda it: f'{esc(it["date"])} — {it["count"]} media items'),
    ]
    plain_facts = [
        ("Peak hour overall", f'{overall.get("peak_hour", "—")}'),
        ("Total media shared", f'{overall["total_media"]:,}'),
        ("Messages deleted", f'{overall["total_deleted"]:,}'),
        ("Messages edited", f'{overall["total_edited"]:,}'),
    ]
    fact_html = "".join(top3_facts) + "".join(
        f'<div class="fact"><div class="k">{esc(k)}</div><div class="v">{v}</div></div>' for k, v in plain_facts
    )
    return f"""
<section id="funfacts">
  {divider("Fun facts")}
  <h2>Small, specific things</h2>
  <p class="lede">Top 3 shown per category.</p>
  <div class="grid grid-2">
    <div>{fact_html}</div>
    {chart_card(charts['media'], 'Message type breakdown')}
  </div>
</section>
"""


def render_explorer(participants):
    options = "".join(f'<option value="{esc(p)}">{esc(p)}</option>' for p in participants)
    return f"""
<section id="explorer" class="explorer">
  {divider("Explorer")}
  <h2>Dig into the archive yourself</h2>
  <p class="lede">These tools run live in your browser against chat_search_data.json — keep that file in the
  same folder as this HTML file. If nothing loads, see the note below.</p>
  <div id="explorer-notice" class="notice" style="display:none">
    Could not load chat_search_data.json. Some browsers block local file loading for security reasons.
    Fix: open a terminal in this folder and run <code>python3 -m http.server 8000</code>, then visit
    <code>http://localhost:8000/</code> and open the report from there.
  </div>

  <div class="card" style="margin-bottom:20px">
    <h3 style="margin-top:0">Word / phrase search</h3>
    <div class="row">
      <input id="searchTerm" type="text" placeholder="e.g. amazing" style="flex:1;min-width:220px">
      <input id="searchVariants" type="text" placeholder="optional variants, comma separated" style="flex:1;min-width:220px">
      <button onclick="runSearch()">Search</button>
    </div>
    <div id="searchResults"></div>
  </div>

  <div class="grid grid-2">
    <div class="card">
      <h3 style="margin-top:0">Date range explorer</h3>
      <div class="row">
        <input id="dateStart" type="date">
        <input id="dateEnd" type="date">
        <button onclick="runDateRange()">Go</button>
      </div>
      <div id="dateRangeResults"></div>
    </div>
    <div class="card">
      <h3 style="margin-top:0">Compare two people</h3>
      <div class="row">
        <select id="personA">{options}</select>
        <select id="personB">{options}</select>
        <button onclick="runCompare()">Compare</button>
      </div>
      <div id="compareResults"></div>
    </div>
  </div>
</section>
"""


HEAD_EXTRA = """
<meta name="viewport" content="width=device-width, initial-scale=1">
"""

JS = r"""
let CHAT_DATA = null;

async function loadData(){
  try {
    const res = await fetch('chat_search_data.json');
    if(!res.ok) throw new Error('bad status');
    CHAT_DATA = await res.json();
  } catch(e){
    document.getElementById('explorer-notice').style.display = 'block';
  }
}
loadData();

function escapeHtml(s){
  return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

function buildVariantRegex(term, variantsStr){
  const terms = [term].concat((variantsStr||'').split(',').map(s=>s.trim()).filter(Boolean));
  const esc = terms.map(t => t.toLowerCase().replace(/[.*+?^${}()|[\]\\]/g,'\\$&'));
  return new RegExp('\\b(?:' + esc.join('|') + ')\\b', 'i');
}

function barRows(bySender, participants){
  const maxV = Math.max(...bySender, 1);
  const order = bySender.map((v,i)=>[v,i]).sort((a,b)=>b[0]-a[0]);
  let html = '';
  for(const [v,i] of order){
    if(v===0) continue;
    const pct = 100*v/maxV;
    html += `<div class="bar-row"><div class="name">${escapeHtml(participants[i])}</div>`
          + `<div class="track"><div class="fill" style="width:${pct}%"></div></div>`
          + `<div class="val">${v}</div></div>`;
  }
  return html;
}

function runSearch(){
  if(!CHAT_DATA) return;
  const term = document.getElementById('searchTerm').value.trim();
  const el = document.getElementById('searchResults');
  if(!term){ el.innerHTML = ''; return; }
  const variants = document.getElementById('searchVariants').value;
  let re;
  try { re = buildVariantRegex(term, variants); } catch(e){ el.innerHTML = '<p>Invalid search term.</p>'; return; }

  const {timestamps, senders, texts, participants} = CHAT_DATA;
  let total = 0;
  const bySender = new Array(participants.length).fill(0);
  let firstIdx = null, lastIdx = null;

  for(let i=0;i<texts.length;i++){
    const t = texts[i];
    if(!t) continue;
    if(re.test(t)){
      total++;
      bySender[senders[i]]++;
      if(firstIdx===null) firstIdx = i;
      lastIdx = i;
    }
  }

  if(total===0){
    el.innerHTML = `<p style="color:var(--muted);margin-top:14px">No matches for "${escapeHtml(term)}".</p>`;
    return;
  }

  function snippet(idx){
    const d = new Date(timestamps[idx]*1000);
    return `<div class="snippet">${escapeHtml(participants[senders[idx]])} — ${d.toLocaleString()}<br>${escapeHtml(texts[idx].slice(0,180))}</div>`;
  }

  el.innerHTML = `
    <p style="margin:14px 0 8px"><span class="pill-count">${total}</span> total occurrences.</p>
    ${barRows(bySender, participants)}
    <div style="margin-top:12px"><b>First use:</b>${snippet(firstIdx)}</div>
    <div style="margin-top:10px"><b>Latest use:</b>${snippet(lastIdx)}</div>
  `;
}

function runDateRange(){
  if(!CHAT_DATA) return;
  const startStr = document.getElementById('dateStart').value;
  const endStr = document.getElementById('dateEnd').value;
  const el = document.getElementById('dateRangeResults');
  if(!startStr || !endStr){ el.innerHTML = ''; return; }
  const start = new Date(startStr+'T00:00:00').getTime()/1000;
  const end = new Date(endStr+'T23:59:59').getTime()/1000;
  const {timestamps, senders, participants} = CHAT_DATA;
  const bySender = new Array(participants.length).fill(0);
  let total = 0;
  const byDay = {};
  for(let i=0;i<timestamps.length;i++){
    const t = timestamps[i];
    if(t>=start && t<=end){
      total++;
      bySender[senders[i]]++;
      const d = new Date(t*1000).toISOString().slice(0,10);
      byDay[d] = (byDay[d]||0)+1;
    }
  }
  if(total===0){ el.innerHTML = '<p style="color:var(--muted);margin-top:14px">No messages in that range.</p>'; return; }
  const days = Math.max(1, Object.keys(byDay).length);
  el.innerHTML = `<p style="margin:14px 0 8px"><span class="pill-count">${total}</span> messages over ${days} active day(s) — avg ${(total/days).toFixed(1)}/day.</p>${barRows(bySender, participants)}`;
}

function statRow(label, a, b, suffix){
  suffix = suffix || '';
  return `<tr><td>${label}</td><td class="pill-count">${a}${suffix}</td><td class="pill-count">${b}${suffix}</td></tr>`;
}

function runCompare(){
  if(!CHAT_DATA) return;
  const a = document.getElementById('personA').value;
  const b = document.getElementById('personB').value;
  const sa = CHAT_DATA.individual_stats[a];
  const sb = CHAT_DATA.individual_stats[b];
  const el = document.getElementById('compareResults');
  if(!sa || !sb) return;
  el.innerHTML = `<table style="margin-top:14px"><thead><tr><th></th><th>${escapeHtml(a)}</th><th>${escapeHtml(b)}</th></tr></thead><tbody>
    ${statRow('Messages', sa.total_messages, sb.total_messages)}
    ${statRow('Unique words', sa.unique_words, sb.unique_words)}
    ${statRow('Avg words/msg', sa.avg_words_per_message, sb.avg_words_per_message)}
    ${statRow('Swear rate /100', sa.swear_rate_per_100, sb.swear_rate_per_100)}
    ${statRow('Laugh rate /100', sa.laugh_rate_per_100, sb.laugh_rate_per_100)}
    ${statRow('Questions asked', sa.question_count, sb.question_count)}
    ${statRow('Tags given', sa.mentions_given, sb.mentions_given)}
    ${statRow('Tags received', sa.mentions_received, sb.mentions_received)}
    ${statRow('Night owl %', sa.night_owl_pct, sb.night_owl_pct, '%')}
    ${statRow('Early bird %', sa.early_bird_pct, sb.early_bird_pct, '%')}
    ${statRow('Double-text rate', sa.double_text_rate_pct, sb.double_text_rate_pct, '%')}
    ${statRow('Chat starts', sa.conversation_starts, sb.conversation_starts)}
    ${statRow('Peak hour', sa.peak_hour, sb.peak_hour, ':00')}
  </tbody></table>`;
}
"""


def render_arc_periods_section(arc_periods, colors):
    """arc_periods: list of dicts, one per arc/mini-arc, each shaped like
    {"label", "seg_type", "name", "description", "start_date", "end_date",
    "duration_days", "bundle", "charts", "cfg"} — see load_arc_segments()
    and the "arcs" block in analyze_chat.py's main(). Renders one nested
    mini-report per period, reusing the SAME render_* functions as the
    main sections and render_last_period_section, with every internal
    element id prefixed "arc{i}-" so none of them collide with each
    other or with the main report's anchors."""
    if not arc_periods:
        return ""

    def rescope(fragment, prefix, *ids):
        for section_id in ids:
            fragment = fragment.replace(f'id="{section_id}"', f'id="{prefix}{section_id}"', 1)
        return fragment

    nav_links = []
    period_blocks = []
    for i, period in enumerate(arc_periods, start=1):
        prefix = f"arc{i}-"
        bundle = period["bundle"]
        charts = {name: img_b64(path) for name, path in period["charts"].items()}
        overall = bundle["overall"]
        individual_stats = bundle["individual_stats"]
        kind = "Arc" if period["seg_type"] == "arc" else "Mini-arc"

        inner = "\n".join([
            rescope(render_overview(overall), prefix, "overview"),
            rescope(render_timing(charts), prefix, "timing"),
            rescope(render_leaderboards(bundle["lb"], charts, individual_stats), prefix, "leaderboards"),
            rescope(render_individuals(charts, individual_stats, colors), prefix, "individuals"),
            rescope(render_words_phrases(bundle["wordstats"], bundle["phrasestats"], period.get("cfg", cfg)), prefix, "words"),
            rescope(render_mentions(bundle["mention_pairs"], charts), prefix, "mentions"),
            rescope(render_funfacts(overall, charts), prefix, "funfacts"),
        ])

        desc_html = f'<p class="lede">{esc(period["description"])}</p>' if period["description"] else ""
        period_blocks.append(f"""
<div id="{prefix}root" style="border:1px dashed var(--line); border-radius:16px; padding:4px 20px 20px; margin-bottom:28px;">
  <h3>{esc(kind)} {i} — {esc(period["name"])}</h3>
  <p class="lede">{esc(period['start_date'])} → {esc(period['end_date'])}
  ({overall['total_messages']:,} messages, {period['duration_days']} days)</p>
  {desc_html}
  {inner}
</div>
""")
        nav_links.append(f'<a href="#{prefix}root">{esc(kind)} {i}</a>')

    return f"""
<section id="arcs">
  {divider("Arcs &amp; Mini-arcs")}
  <h2>Every arc &amp; mini-arc, on its own</h2>
  <p class="lede">The same analysis as above, run separately for each high-activity
  period arc_analyzer.py found in arc_report.txt. Names and descriptions come from
  that file's "ARC NAMES" table — edit them there and re-run to update this report.
  Uses the same looser noise thresholds as the "Last N Days" snapshot, since each of
  these is also a small slice of the full archive. Each arc/mini-arc's "signature
  words/phrases" below compare that slice against the ENTIRE archive (not a per-person
  breakdown) — so what shows up is what that specific stretch of time talked about
  noticeably more than the chat does normally.</p>
  <nav class="tabs" style="margin-bottom:16px;"><div class="wrap">{"".join(nav_links)}</div></nav>
  {"".join(period_blocks)}
</section>
"""


def render_last_period_section(last_period, colors):
    """last_period: {"days": int, "bundle": {...same shape as the main
    bundle...}, "charts": {name: path}}. Renders a nested mini-report using
    the SAME render_* functions as the main sections, with every internal
    element id prefixed "lp-" so they don't collide with the main report's
    anchors."""
    days = last_period["days"]
    bundle = last_period["bundle"]
    charts = {name: img_b64(path) for name, path in last_period["charts"].items()}
    overall = bundle["overall"]
    individual_stats = bundle["individual_stats"]

    def rescope(fragment, *ids):
        for section_id in ids:
            fragment = fragment.replace(f'id="{section_id}"', f'id="lp-{section_id}"', 1)
        return fragment

    inner = "\n".join([
        rescope(render_overview(overall), "overview"),
        rescope(render_timing(charts), "timing"),
        rescope(render_leaderboards(bundle["lb"], charts, individual_stats), "leaderboards"),
        rescope(render_individuals(charts, individual_stats, colors), "individuals"),
        rescope(render_words_phrases(bundle["wordstats"], bundle["phrasestats"], last_period.get("cfg", cfg)), "words"),
        rescope(render_mentions(bundle["mention_pairs"], charts), "mentions"),
        rescope(render_funfacts(overall, charts), "funfacts"),
    ])

    return f"""
<section id="lastperiod">
  {divider(f"Last {days} Days")}
  <h2>Recent snapshot — last {days} days</h2>
  <p class="lede">The same analysis as above, restricted to
  {esc(overall['first_message_ts'][:10])} → {esc(overall['last_message_ts'][:10])}
  ({overall['total_messages']:,} messages). Because this slice has far fewer messages
  than the full archive, it uses looser noise thresholds (shorter minimum word/phrase
  length, lower repeat/signature-message minimums) so it doesn't come back empty —
  see LAST_PERIOD_* in chat_config.py.</p>
  <div style="border:1px dashed var(--line); border-radius:16px; padding:4px 20px 20px;">
  {inner}
  </div>
</section>
"""


SECTION_ORDER = ["overview", "timing", "leaderboards", "individuals", "words", "mentions", "funfacts"]
SECTION_LABELS = {
    "overview": "Overview", "timing": "Timing", "leaderboards": "Leaderboards",
    "individuals": "Individuals", "words": "Words &amp; Phrases", "mentions": "Mentions",
    "funfacts": "Fun facts",
}


def build_html(overall, timedist, individual_stats, lb, wordstats, phrasestats,
                mention_pairs, chart_paths, participants, out_path,
                sections=None, last_period=None, arc_periods=None, cfg_profile=cfg):
    """sections: optional iterable restricting which of SECTION_ORDER (plus
    "lastperiod" and "arcs") get rendered — defaults to everything. The
    Explorer tab is always included since it's a standalone interactive
    tool, not tied to any one static section. last_period: optional dict,
    see render_last_period_section — pass None (or omit "lastperiod" from
    `sections`) to skip that section entirely. arc_periods: optional list
    of dicts, see render_arc_periods_section — pass None/empty (or omit
    "arcs" from `sections`) to skip that section entirely. cfg_profile:
    the (possibly CLI-overridden) namespace wordstats/phrasestats were
    actually computed with, so the Words & Phrases section quotes the
    right thresholds."""
    sections = set(s.lower() for s in sections) if sections is not None else set(SECTION_ORDER) | {"lastperiod", "arcs"}
    charts = {name: img_b64(path) for name, path in chart_paths.items()}

    active = [s for s in SECTION_ORDER if s in sections]
    nav_links = "".join(f'<a href="#{s}">{SECTION_LABELS[s]}</a>' for s in active)
    show_lastperiod = "lastperiod" in sections and last_period and last_period.get("bundle")
    if show_lastperiod:
        nav_links += f'<a href="#lastperiod">Last {last_period["days"]}d</a>'
    show_arcs = "arcs" in sections and bool(arc_periods)
    if show_arcs:
        nav_links += '<a href="#arcs">Arcs</a>'
    nav_links += '<a href="#explorer">Explorer</a>'
    nav = f'<nav class="tabs"><div class="wrap">{nav_links}</div></nav>'

    hero = f"""
    <header class="hero"><div class="wrap">
      <div class="eyebrow">Chat archive report</div>
      <h1>Two years, {overall['total_messages']:,} messages, one group chat.</h1>
      <p class="sub">A statistical portrait of the archive from {overall['first_message_ts'][:10]}
      to {overall['last_message_ts'][:10]} — {overall['total_days_spanned']:,} days,
      {len(participants)} people.</p>
      <div class="stamp">● generated report · scroll or use the tabs below</div>
    </div></header>
    """

    colors_hex = ["#1F6F63", "#E4572E", "#D9A441", "#3E6C9E", "#7A5C7E", "#8FA876",
                  "#B8564A", "#5B8A9E", "#C98A3F", "#6E6A8C", "#3F8F7A", "#C4693F"]
    colors = {p: colors_hex[i % len(colors_hex)] for i, p in enumerate(individual_stats.keys())}

    renderers = {
        "overview": lambda: render_overview(overall),
        "timing": lambda: render_timing(charts),
        "leaderboards": lambda: render_leaderboards(lb, charts, individual_stats),
        "individuals": lambda: render_individuals(charts, individual_stats, colors),
        "words": lambda: render_words_phrases(wordstats, phrasestats, cfg_profile),
        "mentions": lambda: render_mentions(mention_pairs, charts),
        "funfacts": lambda: render_funfacts(overall, charts),
    }

    body_parts = [renderers[s]() for s in active]
    if show_lastperiod:
        body_parts.append(render_last_period_section(last_period, colors))
    if show_arcs:
        body_parts.append(render_arc_periods_section(arc_periods, colors))
    body_parts.append(render_explorer(participants))
    body = "\n".join(body_parts)

    footer = '<footer>Generated with a Python chat analyzer · all stats computed locally from Full_Archive.txt</footer>'

    doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
{HEAD_EXTRA}
<title>Group Chat Report</title>
<style>{CSS}</style>
</head>
<body>
{nav}
{hero}
<div class="wrap">
{body}
</div>
{footer}
<script>{JS}</script>
</body>
</html>"""

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(doc)
    return out_path
