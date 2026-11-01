"""
test_pipeline_smoke.py — end-to-end smoke tests.

Runs the real `control.py` against the bundled sample_data/, exactly as a
user would, in a throwaway sandbox laid out like a real install:

    <tmp>/The-Omar-Files/   <- a copy of this repo (code only)
    <tmp>/data/             <- the data directory, created by `init-data`

This catches breakage in argument parsing, path resolution and the
subprocess wiring between control.py and each tool — not just the
underlying logic (which the other test files cover in isolation). It also
proves the central promise of the two-folder layout: nothing chat-related
is ever written inside the code repo.

Requires the packages in Pipeline/requirements.txt, plus git for the
auto-commit test. Slower than the unit tests; run on its own with:
    cd Pipeline && python3 -m pytest tests/test_pipeline_smoke.py -v
or skip with:
    cd Pipeline && python3 -m pytest tests/ -v -m "not smoke"
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent

pytestmark = pytest.mark.smoke

SAMPLE_FILES = ["01_sample_export_part1.txt", "02_sample_export_part2.txt"]


@pytest.fixture()
def sandbox(tmp_path):
    """(repo_copy, data_dir). The data dir is a sibling named 'data', the
    default location — it doesn't exist yet."""
    repo = tmp_path / "The-Omar-Files"
    shutil.copytree(
        REPO_ROOT, repo,
        ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc", ".pytest_cache"),
    )
    return repo, tmp_path / "data"


def _env(**extra):
    env = {k: v for k, v in os.environ.items() if k != "OMAR_DATA_DIR"}
    env.update(extra)
    return env


def _run(repo, args, env=None):
    return subprocess.run(
        [sys.executable, str(repo / "Pipeline" / "control.py")] + args,
        cwd=repo / "Pipeline", capture_output=True, text=True,
        env=env if env is not None else _env(),
    )


def _set_up(repo, data, with_identities=True, git=False):
    r = _run(repo, ["init-data"] + ([] if git else ["--no-git"]))
    assert r.returncode == 0, r.stdout + r.stderr
    for name in SAMPLE_FILES:
        shutil.copy(repo / "sample_data" / name, data / "Raw_Exports" / name)
    if with_identities:
        shutil.copy(repo / "sample_data" / "identities.sample.json", data / "identities.json")


def test_full_pipeline_on_sample_data(sandbox):
    repo, data = sandbox
    _set_up(repo, data)

    merge = _run(repo, ["merge", "--no-commit"] + SAMPLE_FILES)
    assert merge.returncode == 0, merge.stdout + merge.stderr
    archive = data / "Full_Archive.txt"
    assert archive.exists()
    original_line_count = len(archive.read_text(encoding="utf-8").splitlines())
    assert original_line_count > 0

    reports = _run(repo, ["reports"])
    assert reports.returncode == 0, reports.stdout + reports.stderr
    for expected in ["Full_Archive.pdf", "chat_report.html", "chat_report.pdf",
                     "chat_search_data.json", "arc_report.txt", "arc_timeline.png"]:
        path = data / "Reports" / expected
        assert path.exists(), f"expected Reports/{expected} in the data dir"
        assert path.stat().st_size > 0, f"Reports/{expected} is empty"

    # The code repo must stay free of anything chat-related.
    for stray in ["Full_Archive.txt", "Reports", "Raw_Exports", "identities.json",
                  "Pipeline/identities.json", "Pipeline/normalized_exports",
                  "Pipeline/logs", "config.json"]:
        assert not (repo / stray).exists(), f"{stray} appeared inside the code repo"
    assert not list((repo / "Pipeline" / "Tools").rglob("_chart_cache"))
    assert not list((repo / "Pipeline" / "Tools" / "arc_analyzer").glob("data"))

    # Re-running the same merge adds nothing.
    remerge = _run(repo, ["merge", "--no-commit"] + SAMPLE_FILES)
    assert remerge.returncode == 0, remerge.stdout + remerge.stderr
    assert len(archive.read_text(encoding="utf-8").splitlines()) == original_line_count


def test_update_with_no_files_just_refreshes_reports(sandbox):
    repo, data = sandbox
    _set_up(repo, data)
    assert _run(repo, ["merge", "--no-commit", SAMPLE_FILES[0]]).returncode == 0

    bare = _run(repo, [])
    assert bare.returncode == 0, bare.stdout + bare.stderr
    assert "refreshing reports" in bare.stdout.lower()
    assert (data / "Reports" / "arc_report.txt").exists()


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_merge_auto_commits_to_the_data_repo(sandbox):
    repo, data = sandbox
    _set_up(repo, data, git=True)
    assert (data / ".git").exists()
    for key, val in (("user.name", "Test"), ("user.email", "test@example.com")):
        subprocess.run(["git", "config", key, val], cwd=data, check=True)

    merge = _run(repo, ["merge"] + SAMPLE_FILES)
    assert merge.returncode == 0, merge.stdout + merge.stderr
    log = subprocess.run(["git", "log", "--oneline"], cwd=data,
                         capture_output=True, text=True).stdout
    assert "Merge" in log

    tracked = subprocess.run(["git", "ls-files"], cwd=data,
                             capture_output=True, text=True).stdout.split()
    assert "Full_Archive.txt" in tracked
    assert "identities.json" in tracked
    # derived files stay out of history
    assert not any(t.startswith(("Reports/", "normalized_exports/", ".cache/")) for t in tracked)

    # Re-merging the same exports changes only the merge log (one more
    # history entry), never the archive itself.
    again = _run(repo, ["merge"] + SAMPLE_FILES)
    assert again.returncode == 0
    changed = subprocess.run(["git", "diff", "--name-only", "HEAD~1", "HEAD"], cwd=data,
                             capture_output=True, text=True).stdout.split()
    assert changed == ["logs/merge_log.json"]


def test_data_dir_flag_and_env_var_pick_the_location(sandbox, tmp_path):
    repo, _ = sandbox
    elsewhere = tmp_path / "somewhere" / "my-chat-data"

    r = _run(repo, ["--data-dir", str(elsewhere), "init-data", "--no-git"])
    assert r.returncode == 0, r.stdout + r.stderr
    assert (elsewhere / "Raw_Exports").is_dir()

    via_env = _run(repo, ["doctor"], env=_env(OMAR_DATA_DIR=str(elsewhere)))
    assert str(elsewhere) in via_env.stdout


def test_data_dir_inside_the_repo_is_refused(sandbox):
    repo, _ = sandbox
    r = _run(repo, ["--data-dir", str(repo / "data"), "init-data", "--no-git"])
    assert r.returncode != 0
    assert "inside the code repo" in (r.stdout + r.stderr)
    assert not (repo / "data").exists()


def test_commands_explain_what_to_do_when_there_is_no_data_dir(sandbox):
    repo, data = sandbox
    r = _run(repo, ["merge", "whatever.txt"])
    assert r.returncode != 0
    assert "init-data" in (r.stdout + r.stderr)
    assert not data.exists()


def test_migrate_copies_old_layout_and_verifies(sandbox):
    repo, data = sandbox
    # Fake an install from before the split: data living inside the repo.
    (repo / "Raw_Exports").mkdir(exist_ok=True)
    (repo / "Raw_Exports" / "2026-01_raw.txt").write_text("raw\n", encoding="utf-8")
    (repo / "Full_Archive.txt").write_text("archive\n", encoding="utf-8")
    (repo / "Pipeline" / "identities.json").write_text('{"identities": []}', encoding="utf-8")

    assert _run(repo, ["init-data", "--no-git"]).returncode == 0
    # init-data seeded an example identities.json; the migrated one must not
    # silently overwrite it -- it's reported as a conflict instead.
    first = _run(repo, ["migrate"])
    assert (data / "Full_Archive.txt").read_text(encoding="utf-8") == "archive\n"
    assert (data / "Raw_Exports" / "2026-01_raw.txt").exists()
    assert (repo / "Full_Archive.txt").exists(), "originals must survive a plain migrate"
    assert "CONFLICT" in first.stdout and first.returncode != 0

    # doctor points at the leftovers
    doctor = _run(repo, ["doctor"])
    assert "control.py migrate" in doctor.stdout

    # Resolve the conflict by hand, then remove originals.
    (data / "identities.json").unlink()
    second = _run(repo, ["migrate", "--remove-originals"])
    assert second.returncode == 0, second.stdout + second.stderr
    assert not (repo / "Full_Archive.txt").exists()
    assert not (repo / "Raw_Exports" / "2026-01_raw.txt").exists()
    assert (data / "identities.json").exists()


def test_doctor_passes_once_setup_is_complete(sandbox):
    repo, data = sandbox
    _set_up(repo, data)
    result = _run(repo, ["doctor"])
    assert result.returncode == 0, result.stdout + result.stderr
    assert "[FAIL]" not in result.stdout


def test_doctor_warns_but_does_not_fail_on_fresh_setup(sandbox):
    repo, data = sandbox
    assert _run(repo, ["init-data", "--no-git"]).returncode == 0
    result = _run(repo, ["doctor"])
    assert result.returncode == 0, result.stdout + result.stderr
    assert "[FAIL]" not in result.stdout
    assert "[WARN]" in result.stdout


def test_doctor_fails_clearly_without_a_data_dir(sandbox):
    repo, _ = sandbox
    result = _run(repo, ["doctor"])
    assert result.returncode != 0
    assert "init-data" in result.stdout
