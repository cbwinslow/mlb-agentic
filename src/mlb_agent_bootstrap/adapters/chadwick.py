"""
Chadwick Bureau register adapter.
Syncs the GitHub register repo and copies people-*.csv files to bronze.
"""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from subprocess import run as sp_run, CalledProcessError
from typing import Any, Dict, List


REPO_URL = "https://github.com/chadwickbureau/register"
BRANCH   = "main"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def sync_register(clone_dir: Path, git_bin: str = "git", dry_run: bool = False) -> Dict[str, Any]:
    """Clone or pull the Chadwick register repo."""
    clone_dir.parent.mkdir(parents=True, exist_ok=True)
    if dry_run:
        return {"status": "dry_run", "clone_dir": str(clone_dir)}
    try:
        if (clone_dir / ".git").exists():
            sp_run([git_bin, "-C", str(clone_dir), "fetch", "origin"], check=True, capture_output=True)
            sp_run([git_bin, "-C", str(clone_dir), "checkout", BRANCH], check=True, capture_output=True)
            sp_run([git_bin, "-C", str(clone_dir), "pull", "--ff-only", "origin", BRANCH], check=True, capture_output=True)
            return {"status": "updated", "clone_dir": str(clone_dir)}
        sp_run([git_bin, "clone", "--branch", BRANCH, REPO_URL, str(clone_dir)], check=True, capture_output=True)
        return {"status": "cloned", "clone_dir": str(clone_dir)}
    except CalledProcessError as exc:
        raise RuntimeError(f"git operation failed: {exc.stderr.decode()[:500]}") from exc


def copy_people_files(clone_dir: Path, bronze_dir: Path, dry_run: bool = False) -> List[Dict[str, Any]]:
    """Copy people-*.csv files from the cloned repo to bronze_dir."""
    bronze_dir.mkdir(parents=True, exist_ok=True)
    data_dir = clone_dir / "data"
    results = []
    for src in sorted(data_dir.glob("people-*.csv")):
        dest = bronze_dir / src.name
        if dry_run:
            results.append({"file": src.name, "status": "dry_run"})
            continue
        shutil.copy2(src, dest)
        results.append({"file": src.name, "status": "copied", "sha256": _sha256(dest), "dest": str(dest)})
    return results
