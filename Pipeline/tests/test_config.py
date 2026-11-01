"""
test_config.py — the generic-defaults + data-dir-overrides config model.

chat_config.py and arc_analyzer.py read config.json at import time, so
each scenario runs in a fresh subprocess pointed at its own throwaway
data directory.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

PIPELINE_DIR = Path(__file__).parent.parent
CHAT_DIR = PIPELINE_DIR / "Tools" / "chat_analyzer"
ARC_DIR = PIPELINE_DIR / "Tools" / "arc_analyzer"


def _probe(data_dir, tool_dir, code):
    env = {**os.environ, "OMAR_DATA_DIR": str(data_dir)}
    return subprocess.run(
        [sys.executable, "-c", f"import sys; sys.path.insert(0, {str(tool_dir)!r}); {code}"],
        capture_output=True, text=True, env=env,
    )


def _settings(data_dir, expr):
    r = _probe(data_dir, CHAT_DIR,
               f"import chat_config as c, json; print(json.dumps({expr}))")
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_defaults_are_generic_with_no_config(tmp_path):
    out = _settings(tmp_path / "data", "[c.SWEAR_WORDS, c.EXTRA_STOPWORDS, c.LAST_PERIOD_DAYS]")
    swears, stop, last = out
    assert "shit" in swears
    assert last == 365
    # No group-specific words baked into the shipped defaults.
    blob = " ".join(swears + stop).lower()
    for personal in ("akif", "omar", "nasser", "kutta", "mothertrucker"):
        assert personal not in blob


def test_extend_and_override_come_from_config_json(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "config.json").write_text(json.dumps({
        "chat_analyzer": {
            "_about": "comment",
            "extend": {"SWEAR_WORDS": ["zonk"], "LAUGH_WORDS": ["kek"]},
            "override": {"TOP_N": 7, "NIGHT_OWL_HOURS": [1, 4]},
        }
    }), encoding="utf-8")
    swears, laughs, top_n, owl = _settings(
        data, "[c.SWEAR_WORDS, c.LAUGH_WORDS, c.TOP_N, c.NIGHT_OWL_HOURS]")
    assert "zonk" in swears and "shit" in swears  # extended, not replaced
    assert "kek" in laughs
    assert top_n == 7
    assert owl == [1, 4] or owl == (1, 4)


def test_member_names_become_stopwords_automatically(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "identities.json").write_text(json.dumps({"identities": [
        {"name": "Zephyrine", "aliases": ["923001234567@s.whatsapp.net", "Zeph Q",
                                          "+92 300 1234567"]},
    ]}), encoding="utf-8")
    (stop,) = _settings(data, "[c.EXTRA_STOPWORDS]")
    assert "zephyrine" in stop and "zeph" in stop
    assert not any(any(ch.isdigit() for ch in w) for w in stop), "phone numbers leaked in"


def test_unknown_chat_setting_is_a_loud_error(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "config.json").write_text(json.dumps(
        {"chat_analyzer": {"override": {"NOT_A_SETTING": 1}}}), encoding="utf-8")
    r = _probe(data, CHAT_DIR, "import chat_config")
    assert r.returncode != 0
    assert "NOT_A_SETTING" in r.stderr


def test_arc_defaults_are_generic_and_overridable(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    r = _probe(data, ARC_DIR, "import arc_analyzer as a; print(a.CONFIG.ROLLING_WINDOW_DAYS, a.CONFIG.ARC_PEAK_MULTIPLIER)")
    assert r.returncode == 0, r.stderr
    assert r.stdout.split() == ["14", "2.0"]

    (data / "config.json").write_text(json.dumps(
        {"arc_analyzer": {"ROLLING_WINDOW_DAYS": 21, "ARC_PEAK_MULTIPLIER": 1.5}}), encoding="utf-8")
    r = _probe(data, ARC_DIR, "import arc_analyzer as a; print(a.CONFIG.ROLLING_WINDOW_DAYS, a.CONFIG.ARC_PEAK_MULTIPLIER)")
    assert r.returncode == 0, r.stderr
    assert r.stdout.split() == ["21", "1.5"]


def test_arc_unknown_setting_is_a_loud_error(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "config.json").write_text(json.dumps(
        {"arc_analyzer": {"ROLLING_WINDOW_DYAS": 21}}), encoding="utf-8")
    r = _probe(data, ARC_DIR, "import arc_analyzer")
    assert r.returncode != 0
    assert "ROLLING_WINDOW_DYAS" in (r.stderr + r.stdout)


def test_arc_parser_only_drops_system_senders_not_messages_containing_words(tmp_path):
    """Regression: a message that merely contains 'left' / 'added' used to be
    dropped from arc stats as if it were a group event."""
    data = tmp_path / "data"
    data.mkdir()
    archive = tmp_path / "a.txt"
    archive.write_text(
        "01-Jan-2025, 10:00 - Alice: I left my keys at home\n"
        "01-Jan-2025, 10:01 - Bob: I added you to the doc\n"
        "01-Jan-2025, 10:02 - [SYSTEM] Alice added Bob\n"
        "01-Jan-2025, 10:03 - Alice: ok\n", encoding="utf-8")
    r = _probe(data, ARC_DIR,
               f"import arc_analyzer as a; print(len(a.parse_chat({str(archive)!r})))")
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "3"
