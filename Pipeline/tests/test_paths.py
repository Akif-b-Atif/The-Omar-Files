"""
test_paths.py — unit tests for omar_paths.py (where the data lives).
"""
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import omar_paths  # noqa: E402


@pytest.fixture()
def data_env(tmp_path, monkeypatch):
    path = tmp_path / "data"
    monkeypatch.setenv(omar_paths.ENV_VAR, str(path))
    return path


def test_env_var_selects_the_data_dir(data_env):
    assert omar_paths.resolve_data_dir() == data_env.resolve()


def test_default_is_a_sibling_called_data(monkeypatch):
    monkeypatch.delenv(omar_paths.ENV_VAR, raising=False)
    assert omar_paths.resolve_data_dir() == (omar_paths.REPO_ROOT.parent / "data").resolve()


def test_data_dir_inside_the_repo_is_refused(monkeypatch):
    monkeypatch.setenv(omar_paths.ENV_VAR, str(omar_paths.REPO_ROOT / "data"))
    with pytest.raises(omar_paths.DataDirError):
        omar_paths.resolve_data_dir()


def test_require_paths_explains_how_to_create_it(data_env):
    with pytest.raises(omar_paths.DataDirError) as exc:
        omar_paths.require_paths()
    assert "init-data" in str(exc.value)


def test_init_data_dir_creates_layout_and_is_idempotent(data_env):
    omar_paths.init_data_dir(init_git=False)
    paths = omar_paths.get_paths()
    for d in (paths.raw_exports, paths.normalized, paths.logs, paths.reports,
              paths.chart_cache, paths.arc_data):
        assert d.is_dir()
    assert paths.identities.exists() and paths.config.exists()
    assert "Reports/" in (paths.root / ".gitignore").read_text(encoding="utf-8")

    # A re-run must never clobber what the user has edited.
    paths.identities.write_text('{"identities": [{"name": "Zed", "aliases": []}]}', encoding="utf-8")
    omar_paths.init_data_dir(init_git=False)
    assert "Zed" in paths.identities.read_text(encoding="utf-8")


def test_user_config_missing_is_empty(data_env):
    assert omar_paths.load_user_config() == {}
    assert omar_paths.user_config_section("chat_analyzer") == {}


def test_user_config_sections_drop_comment_keys(data_env):
    data_env.mkdir()
    (data_env / "config.json").write_text(json.dumps({
        "_about": "ignored",
        "arc_analyzer": {"_note": "ignored", "ROLLING_WINDOW_DAYS": 21},
    }), encoding="utf-8")
    assert omar_paths.user_config_section("arc_analyzer") == {"ROLLING_WINDOW_DAYS": 21}


def test_broken_config_is_a_loud_error(data_env):
    data_env.mkdir()
    (data_env / "config.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(omar_paths.DataDirError):
        omar_paths.load_user_config()


def test_commit_data_skips_quietly_when_not_a_git_repo(data_env):
    omar_paths.init_data_dir(init_git=False)
    ok, note = omar_paths.commit_data("anything")
    assert ok is False and "git repo" in note
