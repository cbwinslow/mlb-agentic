"""
Retrosheet source adapter.
Downloads traditional event archives and CSV bundles from retrosheet.org,
then lands raw files in the bronze layer without any transformation.
"""
from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path
from typing import Any, Dict, List
import requests


_EVENT_BASE = "https://www.retrosheet.org"
_CSV_BASE   = "https://www.retrosheet.org/downloads"
_TRADITIONAL_YEARS = list(range(1871, 2026))


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _download_file(url: str, dest: Path, timeout: int = 120, retries: int = 3) -> str:
    dest.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, timeout=timeout, stream=True)
            resp.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    f.write(chunk)
            return _sha256(dest)
        except Exception as exc:
            if attempt == retries:
                raise RuntimeError(f"Failed to download {url} after {retries} attempts: {exc}") from exc
    return ""


def download_traditional_archives(
    download_dir: Path,
    seasons=None,
    timeout: int = 120,
    retries: int = 3,
    dry_run: bool = False,
) -> List[Dict[str, Any]]:
    """Download per-season event archive zip files from Retrosheet."""
    results = []
    target_seasons = seasons or _TRADITIONAL_YEARS
    for year in target_seasons:
        url = f"{_EVENT_BASE}/{year}eve.zip"
        dest = download_dir / f"{year}eve.zip"
        if dry_run:
            results.append({"year": year, "url": url, "status": "dry_run", "dest": str(dest)})
            continue
        if dest.exists():
            results.append({"year": year, "url": url, "status": "cached", "dest": str(dest), "sha256": _sha256(dest)})
            continue
        try:
            sha = _download_file(url, dest, timeout=timeout, retries=retries)
            results.append({"year": year, "url": url, "status": "downloaded", "dest": str(dest), "sha256": sha})
        except Exception as exc:
            results.append({"year": year, "url": url, "status": "skipped", "reason": str(exc)})
    return results


def extract_traditional_archives(download_dir: Path, extract_dir: Path, dry_run: bool = False) -> List[Dict[str, Any]]:
    """Extract all downloaded zip archives to extract_dir."""
    results = []
    for zp in sorted(download_dir.glob("*.zip")):
        if dry_run:
            results.append({"archive": zp.name, "status": "dry_run"})
            continue
        try:
            with zipfile.ZipFile(zp) as z:
                z.extractall(extract_dir)
            results.append({"archive": zp.name, "status": "extracted", "dest": str(extract_dir)})
        except Exception as exc:
            results.append({"archive": zp.name, "status": "failed", "reason": str(exc)})
    return results


def download_csv_bundles(
    download_dir: Path,
    timeout: int = 120,
    retries: int = 3,
    dry_run: bool = False,
) -> List[Dict[str, Any]]:
    """Download Retrosheet processed CSV bundles."""
    bundles = [
        "games_post.zip", "games_regular.zip",
        "batting_regular.zip", "pitching_regular.zip",
        "fielding_regular.zip", "batting_post.zip", "pitching_post.zip",
    ]
    results = []
    for bundle in bundles:
        url = f"{_CSV_BASE}/{bundle}"
        dest = download_dir / bundle
        if dry_run:
            results.append({"bundle": bundle, "url": url, "status": "dry_run"})
            continue
        if dest.exists():
            results.append({"bundle": bundle, "url": url, "status": "cached", "sha256": _sha256(dest)})
            continue
        try:
            sha = _download_file(url, dest, timeout=timeout, retries=retries)
            results.append({"bundle": bundle, "url": url, "status": "downloaded", "sha256": sha})
        except Exception as exc:
            results.append({"bundle": bundle, "url": url, "status": "skipped", "reason": str(exc)})
    return results
