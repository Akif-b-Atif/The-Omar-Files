"""
test_pipeline_smoke.py — end-to-end smoke test.

Runs `control.py merge` + `control.py reports` against the real
sample_data/ (the same walkthrough in sample_data/README.md), in a
throwaway copy of the repo, and checks that every promised output file
actually gets written and that re-merging the same exports a second
time adds nothing new.

This intentionally shells out to `python3 control.py ...` exactly as a
user would, rather than importing control.py's functions directly, so
it also catches breakage in argument parsing / file resolution / the
subprocess wiring between control.py and each tool — not just the
underlying logic (which the other test files cover in isolation).

Requires the packages in Pipeline/requirements.txt to be installed.
Slower than the unit tests (spins up several subprocesses and renders
real charts/PDFs) — run it on its own with:
    cd Pipeline && python3 -m pytest tests/test_pipeline_smoke.py -v
or skip it for a fast inner loop with:
    cd Pipeline && python3 -m pytest tests/ -v -m "not smoke"
"""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent

pytestmark = pytest.mark.smoke


@pytest.fixture()
def sandbox_repo(tmp_path):
    """A throwaway copy of the whole repo, so this test can never touch
    a real archive or a real identities.json."""
    dest = tmp_path / "repo"
    shutil.copytree(
        REPO_ROOT,
        dest,
        ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
    )
    return dest


def _run(args, cwd):
    return subprocess.run(
        [sys.executable, "control.py"] + args,
        cwd=cwd, capture_output=True, text=True,
    )


def test_full_pipeline_on_sample_data(sandbox_repo):
    pipeline_dir = sandbox_repo / "Pipeline"
    raw_exports_dir = sandbox_repo / "Raw_Exports"
    sample_dir = sandbox_repo / "sample_data"

    shutil.copy(sample_dir / "01_sample_export_part1.txt", raw_exports_dir)
    shutil.copy(sample_dir / "02_sample_export_part2.txt", raw_exports_dir)
    shutil.copy(sample_dir / "identities.sample.json", pipeline_dir / "identities.json")

    merge = _run(
        ["merge", "01_sample_export_part1.txt", "02_sample_export_part2.txt"],
        cwd=pipeline_dir,
    )
    assert merge.returncode == 0, merge.stdout + merge.stderr
    assert (sandbox_repo / "Full_Archive.txt").exists()
    archive_text = (sandbox_repo / "Full_Archive.txt").read_text(encoding="utf-8")
    assert archive_text.strip()  # not empty
    original_line_count = len(archive_text.splitlines())

    reports = _run(["reports"], cwd=pipeline_dir)
    assert reports.returncode == 0, reports.stdout + reports.stderr

    reports_dir = sandbox_repo / "Reports"
    for expected in [
        "Full_Archive.pdf",
        "chat_report.html",
        "chat_report.pdf",
        "chat_search_data.json",
        "arc_report.txt",
        "arc_timeline.png",
    ]:
        path = reports_dir / expected
        assert path.exists(), f"expected Reports/{expected} to be written"
        assert path.stat().st_size > 0, f"Reports/{expected} was written but is empty"

    # The project root itself should stay uncluttered: only Full_Archive.txt
    # (the archive) belongs there, not any of the generated reports.
    for leftover in ["Full_Archive.pdf", "chat_report.html", "chat_report.pdf",
                      "chat_search_data.json", "arc_report.txt", "arc_timeline.png"]:
        assert not (sandbox_repo / leftover).exists(), \
            f"{leftover} was written to the project root instead of Reports/"

    # Re-running the same merge should add nothing (see 3_merge_export.py's
    # "safe to re-run" guarantee).
    remerge = _run(
        ["merge", "01_sample_export_part1.txt", "02_sample_export_part2.txt"],
        cwd=pipeline_dir,
    )
    assert remerge.returncode == 0, remerge.stdout + remerge.stderr
    archive_text_after = (sandbox_repo / "Full_Archive.txt").read_text(encoding="utf-8")
    assert len(archive_text_after.splitlines()) == original_line_count


def test_update_with_no_files_just_refreshes_reports(sandbox_repo):
    """`control.py` (or `control.py update` with no filenames) should
    refresh reports from whatever's already in the archive, without
    requiring a new export — this is the documented no-argument
    default in control.py's own --help text."""
    pipeline_dir = sandbox_repo / "Pipeline"
    raw_exports_dir = sandbox_repo / "Raw_Exports"
    sample_dir = sandbox_repo / "sample_data"

    shutil.copy(sample_dir / "01_sample_export_part1.txt", raw_exports_dir)
    shutil.copy(sample_dir / "identities.sample.json", pipeline_dir / "identities.json")
    merge = _run(["merge", "01_sample_export_part1.txt"], cwd=pipeline_dir)
    assert merge.returncode == 0, merge.stdout + merge.stderr

    bare = _run([], cwd=pipeline_dir)
    assert bare.returncode == 0, bare.stdout + bare.stderr
    assert "refreshing reports" in bare.stdout.lower()
    assert (sandbox_repo / "Reports" / "arc_report.txt").exists()


def test_doctor_passes_once_setup_is_complete(sandbox_repo):
    pipeline_dir = sandbox_repo / "Pipeline"
    shutil.copy(
        sandbox_repo / "sample_data" / "identities.sample.json",
        pipeline_dir / "identities.json",
    )
    result = _run(["doctor"], cwd=pipeline_dir)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "[FAIL]" not in result.stdout


def test_doctor_warns_but_does_not_fail_on_fresh_clone(sandbox_repo):
    """No identities.json, no Raw_Exports/ contents, no archive yet —
    everything a brand new clone looks like. Should WARN, not FAIL,
    since none of that blocks doctor itself from running."""
    pipeline_dir = sandbox_repo / "Pipeline"
    result = _run(["doctor"], cwd=pipeline_dir)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "[FAIL]" not in result.stdout
    assert "[WARN]" in result.stdout
