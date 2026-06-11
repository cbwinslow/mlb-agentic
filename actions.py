from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Dict


def ensure_directories(args: Dict[str, Any], context: Dict[str, Any]) -> str:
    for path in args.get("paths", []):
        Path(path).mkdir(parents=True, exist_ok=True)
    return "directories ensured"


def http_get(args: Dict[str, Any], context: Dict[str, Any]) -> str:
    import requests
    url = args["url"]
    save_as = args["save_as"]
    out_dir = Path(context["run_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    res = requests.get(url, timeout=context.get("request_timeout_seconds", 120))
    res.raise_for_status()
    (out_dir / save_as).write_text(res.text, encoding="utf-8")
    return f"saved {save_as}"


def git_sync(args: Dict[str, Any], context: Dict[str, Any]) -> str:
    from subprocess import run
    repo_url = args["repo_url"]
    destination_dir = Path(args["destination_dir"])
    branch = args.get("branch", "main")
    if destination_dir.exists() and (destination_dir / ".git").exists():
        run([context.get("git_bin", "git"), "-C", str(destination_dir), "fetch", "origin"], check=True)
        run([context.get("git_bin", "git"), "-C", str(destination_dir), "checkout", branch], check=True)
        run([context.get("git_bin", "git"), "-C", str(destination_dir), "pull", "--ff-only", "origin", branch], check=True)
        return "repo updated"
    destination_dir.parent.mkdir(parents=True, exist_ok=True)
    run([context.get("git_bin", "git"), "clone", "--branch", branch, repo_url, str(destination_dir)], check=True)
    return "repo cloned"


def copy_matching_files(args: Dict[str, Any], context: Dict[str, Any]) -> str:
    source_dir = Path(args["source_dir"])
    destination_dir = Path(args["destination_dir"])
    destination_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for pattern in args.get("include_globs", []):
        for src in source_dir.glob(pattern):
            if src.is_file():
                shutil.copy2(src, destination_dir / src.name)
                count += 1
    return f"copied {count} files"


def build_date_chunks(args: Dict[str, Any], context: Dict[str, Any]) -> str:
    from datetime import datetime, timedelta
    start_date = datetime.strptime(args["start_date"], "%Y-%m-%d").date()
    end_date = datetime.strptime(args["end_date"], "%Y-%m-%d").date()
    chunk_days = int(args["chunk_days"])
    chunks = []
    cur = start_date
    while cur <= end_date:
        chunk_end = min(cur + timedelta(days=chunk_days - 1), end_date)
        chunks.append({"start_date": cur.isoformat(), "end_date": chunk_end.isoformat()})
        cur = chunk_end + timedelta(days=1)
    out = Path(context["run_dir"]) / "date_chunks.json"
    out.write_text(json.dumps(chunks, indent=2), encoding="utf-8")
    return f"built {len(chunks)} chunks"


def log_message(args: Dict[str, Any], context: Dict[str, Any]) -> str:
    return args.get("message", "")


ACTION_REGISTRY = {
    "ensure_directories": ensure_directories,
    "http_get": http_get,
    "git_sync": git_sync,
    "copy_matching_files": copy_matching_files,
    "build_date_chunks": build_date_chunks,
    "log_message": log_message,
}
