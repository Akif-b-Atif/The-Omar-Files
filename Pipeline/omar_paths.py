"""
omar_paths.py
-------------
The ONE place that knows where things live.

This repo contains only code. Everything that belongs to a specific chat —
raw exports, the archive, identities, reports, caches, your personal
settings — lives in a separate "data directory" that sits OUTSIDE this
repo's folder, so a stray `git add .` here can never pick any of it up:

    some-folder/
    ├── The-Omar-Files/     <- this repo (code only, safe to publish)
    └── data/               <- your data (its own, private git repo)

Where the data directory is, in priority order:
    1. `--data-dir PATH` on control.py (it exports it for every step), or
    2. the OMAR_DATA_DIR environment variable, or
    3. `data/` as a sibling of this repo's folder (the default above).

A data directory inside this repo's own folder is refused on purpose.

Layout of the data directory:

    data/
    ├── config.json          <- YOUR settings (word lists, thresholds...)
    ├── identities.json      <- who is who (real names/numbers: private!)
    ├── Full_Archive.txt     <- THE archive
    ├── Raw_Exports/         <- every raw export, kept forever
    ├── normalized_exports/  <- derived (rebuildable)
    ├── logs/merge_log.json
    ├── Reports/             <- derived (rebuildable)
    └── .cache/              <- derived (rebuildable)

Standard library only, so every script in the pipeline can import it.
"""
import json
import os
import shutil
import subprocess
from pathlib import Path

PIPELINE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PIPELINE_DIR.parent
TOOLS_DIR = PIPELINE_DIR / "Tools"
FONTS_DIR = TOOLS_DIR / "fonts"

ENV_VAR = "OMAR_DATA_DIR"
DEFAULT_DATA_DIRNAME = "data"

# Everything below can be rebuilt from Raw_Exports/ + identities.json +
# config.json, so it's kept out of the data repo's git history.
DATA_GITIGNORE = """\
# Derived files -- all rebuildable from Raw_Exports/ + identities.json +
# config.json, so they stay out of git history.
normalized_exports/
Reports/
.cache/

# Never track a phone-backup database or its key material here.
*.db
*.db-wal
*.db-shm
msgstore*
*.key
*.crypt*

__pycache__/
.DS_Store
Thumbs.db
"""


class DataDirError(RuntimeError):
    """The data directory is missing or in an unsafe place."""


def _inside(child, parent):
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def resolve_data_dir():
    """Returns the data directory as an absolute Path (it may not exist
    yet). Raises DataDirError if it's inside this repo's own folder."""
    env = os.environ.get(ENV_VAR, "").strip()
    if env:
        path = Path(env).expanduser().resolve()
    else:
        path = (REPO_ROOT.parent / DEFAULT_DATA_DIRNAME).resolve()
    if _inside(path, REPO_ROOT.resolve()):
        raise DataDirError(
            f"The data directory ({path}) is inside the code repo "
            f"({REPO_ROOT}). That defeats the point of keeping them apart "
            f"-- pick a folder outside it, e.g. {REPO_ROOT.parent / DEFAULT_DATA_DIRNAME}"
        )
    return path


class DataPaths:
    """Every path the pipeline reads or writes, derived from one root."""

    def __init__(self, root):
        self.root = Path(root)
        self.config = self.root / "config.json"
        self.identities = self.root / "identities.json"
        self.archive = self.root / "Full_Archive.txt"
        self.raw_exports = self.root / "Raw_Exports"
        self.normalized = self.root / "normalized_exports"
        self.logs = self.root / "logs"
        self.merge_log = self.logs / "merge_log.json"
        self.reports = self.root / "Reports"
        self.cache = self.root / ".cache"
        self.chart_cache = self.cache / "chart_cache"
        self.arc_data = self.cache / "arc"

    def ensure_dirs(self):
        for d in (self.raw_exports, self.normalized, self.logs,
                  self.reports, self.chart_cache, self.arc_data):
            d.mkdir(parents=True, exist_ok=True)


def get_paths():
    """The DataPaths for the current environment. Does not create anything."""
    return DataPaths(resolve_data_dir())


def require_paths():
    """Like get_paths(), but the data directory must already exist --
    otherwise it explains how to create one instead of silently making a
    stray folder somewhere."""
    paths = get_paths()
    if not paths.root.is_dir():
        raise DataDirError(
            f"No data directory at {paths.root}.\n"
            f"  Create one with:   python3 control.py init-data\n"
            f"  Already have data in this repo from an older version? Then:\n"
            f"                     python3 control.py init-data && python3 control.py migrate\n"
            f"  Keeping it elsewhere? Pass --data-dir PATH or set {ENV_VAR}."
        )
    return paths


# ---------------------------------------------------------------------------
# User config (data/config.json)
# ---------------------------------------------------------------------------

def load_user_config():
    """Reads data/config.json. Returns {} if there isn't one (every setting
    then keeps its generic default). A broken file raises a clear error
    rather than silently ignoring your settings."""
    try:
        path = get_paths().config
    except DataDirError:
        return {}
    if not path.is_file():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise DataDirError(f"{path} isn't valid JSON: {e}")
    if not isinstance(data, dict):
        raise DataDirError(f"{path} must contain a JSON object at the top level.")
    return data


def user_config_section(name):
    """One top-level section of config.json (e.g. "chat_analyzer"), as a
    dict. Keys starting with "_" are treated as comments and dropped."""
    section = load_user_config().get(name, {})
    if not isinstance(section, dict):
        raise DataDirError(f"config.json: \"{name}\" must be a JSON object.")
    return {k: v for k, v in section.items() if not k.startswith("_")}


# ---------------------------------------------------------------------------
# Scaffolding a fresh data directory
# ---------------------------------------------------------------------------

def _git_available():
    return shutil.which("git") is not None


def is_git_repo(path):
    return (Path(path) / ".git").exists()


def init_data_dir(init_git=True):
    """Creates the data directory skeleton (safe to re-run: never
    overwrites an existing file). Returns a list of human-readable
    lines describing what it did."""
    paths = get_paths()
    done = []
    existed = paths.root.is_dir()
    paths.root.mkdir(parents=True, exist_ok=True)
    paths.ensure_dirs()
    done.append(f"{'Using existing' if existed else 'Created'} data directory: {paths.root}")

    gi = paths.root / ".gitignore"
    if not gi.exists():
        gi.write_text(DATA_GITIGNORE, encoding="utf-8")
        done.append("Wrote .gitignore (derived files stay out of git)")

    for src_name, dest in (("config.example.json", paths.config),
                           ("identities.example.json", paths.identities)):
        src = PIPELINE_DIR / src_name
        if src.is_file() and not dest.exists():
            shutil.copyfile(src, dest)
            done.append(f"Copied {src_name} -> {dest.name} (edit it for your group)")

    if init_git:
        if is_git_repo(paths.root):
            done.append("Already a git repo")
        elif not _git_available():
            done.append("git not found -- skipped `git init` (install git for "
                        "automatic history of your archive)")
        else:
            r = subprocess.run(["git", "init", "-q"], cwd=paths.root,
                               capture_output=True, text=True)
            if r.returncode == 0:
                done.append("Ran `git init` -- keep this repo PRIVATE (it holds your chat)")
            else:
                done.append(f"`git init` failed: {r.stderr.strip()}")
    return done


# ---------------------------------------------------------------------------
# Auto-commit of the data repo
# ---------------------------------------------------------------------------

def commit_data(message):
    """Commits whatever changed in the data repo (never pushes). Returns
    (ok, note). Quietly does nothing if the data dir isn't a git repo or
    nothing changed. A failure here never affects the archive itself."""
    paths = get_paths()
    if not is_git_repo(paths.root):
        return False, "data dir isn't a git repo -- skipped auto-commit"
    if not _git_available():
        return False, "git not found -- skipped auto-commit"

    def git(*args):
        return subprocess.run(["git", *args], cwd=paths.root,
                              capture_output=True, text=True)

    if git("add", "-A").returncode != 0:
        return False, "`git add` failed -- skipped auto-commit"
    if not git("status", "--porcelain").stdout.strip():
        return True, "nothing new to commit"
    r = git("commit", "-q", "-m", message)
    if r.returncode != 0:
        return False, ("`git commit` failed (is user.name / user.email set?): "
                       + (r.stderr.strip() or r.stdout.strip()))
    return True, f"committed to {paths.root.name}/: {message}"


# ---------------------------------------------------------------------------
# Migrating from the old in-repo layout
# ---------------------------------------------------------------------------

def _legacy_map():
    """(old location, new location) pairs. Directories map to directories."""
    p = get_paths()
    return [
        (REPO_ROOT / "Full_Archive.txt", p.archive),
        (PIPELINE_DIR / "identities.json", p.identities),
        (REPO_ROOT / "Raw_Exports", p.raw_exports),
        (PIPELINE_DIR / "normalized_exports", p.normalized),
        (PIPELINE_DIR / "logs", p.logs),
        (REPO_ROOT / "Reports", p.reports),
        (TOOLS_DIR / "chat_analyzer" / "_chart_cache", p.chart_cache),
        (TOOLS_DIR / "arc_analyzer" / "data", p.arc_data),
    ]


def _sha256(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def migrate_legacy(remove_originals=False):
    """Copies data from the old in-repo layout into the data directory,
    verifying every copy by checksum. Originals are left alone unless
    remove_originals=True AND that file's copy verified. Never overwrites
    a different file already in the data dir. Returns (lines, ok)."""
    paths = require_paths()
    paths.ensure_dirs()
    lines, ok, copied = [], True, 0

    jobs = []
    for old, new in _legacy_map():
        if old.is_file():
            jobs.append((old, new))
        elif old.is_dir():
            for f in sorted(old.rglob("*")):
                if f.is_file() and f.name != ".gitkeep":
                    jobs.append((f, new / f.relative_to(old)))

    if not jobs:
        return ["Nothing to migrate: no data found in the old in-repo locations."], True

    for src, dest in jobs:
        rel = src.relative_to(REPO_ROOT)
        if dest.exists():
            if _sha256(src) == _sha256(dest):
                lines.append(f"  same    {rel} (already in data dir)")
                verified = True
            else:
                lines.append(f"  CONFLICT {rel}: a DIFFERENT file is already at "
                             f"{dest} -- left both untouched, sort this one out by hand")
                ok = False
                continue
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            verified = _sha256(src) == _sha256(dest)
            if verified:
                copied += 1
                lines.append(f"  copied  {rel}")
            else:
                lines.append(f"  FAILED  {rel}: checksum mismatch after copy -- "
                             f"removed the bad copy, original untouched")
                dest.unlink()
                ok = False
                continue
        if remove_originals and verified:
            src.unlink()

    lines.append(f"\n{copied} file(s) copied into {paths.root}.")
    if ok and not remove_originals:
        lines.append("Originals were NOT deleted. Once you've checked everything "
                     "(`python3 control.py doctor`, then `python3 control.py reports`), "
                     "re-run with `migrate --remove-originals` to clear them out of the repo folder.")
    return lines, ok
