"""
Builds chat_search_data.json — a compact, columnar export of every real
text message, used client-side by the HTML report's dynamic search /
date-range explorer / person-comparison tools. Kept separate from the
main report JSON so the HTML file itself stays light.
"""
import json


def build_search_data(df, participants, individual_stats, overall, timedist):
    real = df[(~df["is_system"]) & (df["is_real_text"] | df["is_media"] | df["is_deleted"])].sort_values("timestamp")

    sender_index = {p: i for i, p in enumerate(participants)}
    timestamps = []
    senders = []
    texts = []
    flags = []  # 0 normal, 1 media, 2 deleted

    for row in real.itertuples(index=False):
        sender = getattr(row, "sender")
        if sender not in sender_index:
            continue
        timestamps.append(int(row.timestamp.timestamp()))
        senders.append(sender_index[sender])
        if row.is_media:
            texts.append("")
            flags.append(1)
        elif row.is_deleted:
            texts.append("")
            flags.append(2)
        else:
            texts.append(row.text.replace("\n", " ").strip())
            flags.append(0)

    data = {
        "participants": participants,
        "timestamps": timestamps,   # unix seconds, parallel arrays
        "senders": senders,         # index into participants
        "texts": texts,
        "flags": flags,
        "individual_stats": individual_stats,
        "overall": overall,
        "time_distribution": {
            "by_hour": timedist["by_hour"],
            "by_weekday": timedist["by_weekday"],
        },
    }
    return data


def write_search_json(data, out_path):
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
