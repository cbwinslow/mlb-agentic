"""
Statcast / Baseball Savant adapter.
Downloads chunked Parquet exports via pybaseball and lands raw files in bronze.
"""
from __future__ import annotations

import hashlib
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Tuple


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def build_chunks(start: date, end: date, chunk_days: int) -> List[Tuple[date, date]]:
    chunks: List[Tuple[date, date]] = []
    cur = start
    while cur <= end:
        chunk_end = min(cur + timedelta(days=chunk_days - 1), end)
        chunks.append((cur, chunk_end))
        cur = chunk_end + timedelta(days=1)
    return chunks


def download_statcast_chunk(
    start_dt: date,
    end_dt: date,
    download_dir: Path,
    timeout: int = 300,
    dry_run: bool = False,
) -> Dict[str, Any]:
    filename = f"statcast_{start_dt.isoformat()}_{end_dt.isoformat()}.parquet"
    dest = download_dir / filename
    if dry_run:
        return {"start": str(start_dt), "end": str(end_dt), "status": "dry_run", "dest": str(dest)}
    if dest.exists():
        return {"start": str(start_dt), "end": str(end_dt), "status": "cached", "dest": str(dest), "sha256": _sha256(dest)}
    try:
        import pybaseball
        pybaseball.cache.enable()
        df = pybaseball.statcast(start_dt=start_dt.isoformat(), end_dt=end_dt.isoformat())
        if df is None or df.empty:
            return {"start": str(start_dt), "end": str(end_dt), "status": "empty"}
        download_dir.mkdir(parents=True, exist_ok=True)
        df.to_parquet(dest, index=False, engine="pyarrow")
        return {"start": str(start_dt), "end": str(end_dt), "status": "downloaded", "rows": len(df), "sha256": _sha256(dest)}
    except Exception as exc:
        return {"start": str(start_dt), "end": str(end_dt), "status": "failed", "reason": str(exc)}


def download_statcast_range(
    start: date, end: date, download_dir: Path,
    chunk_days: int = 5, timeout: int = 300, dry_run: bool = False,
) -> List[Dict[str, Any]]:
    chunks = build_chunks(start, end, chunk_days)
    return [download_statcast_chunk(s, e, download_dir, timeout=timeout, dry_run=dry_run) for s, e in chunks]
