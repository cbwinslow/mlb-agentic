"""
Action registry.
All actions receive (args: dict, context: dict) and return a str summary.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Dict

from .adapters import retrosheet as rs_adapter
from .adapters import chadwick as cw_adapter
from .adapters import statcast as sc_adapter
from .loaders import bronze_postgres as bronze


def ensure_directories(args: Dict[str, Any], ctx: Dict[str, Any]) -> str:
    for p in args.get("paths", []):
        Path(p).mkdir(parents=True, exist_ok=True)
    return f"ensured {len(args.get('paths', []))} directories"


def log_message(args: Dict[str, Any], ctx: Dict[str, Any]) -> str:
    return args.get("message", "")


def write_json(args: Dict[str, Any], ctx: Dict[str, Any]) -> str:
    dest = Path(args["dest"])
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(args["data"], indent=2), encoding="utf-8")
    return f"wrote {dest}"


def retrosheet_download_traditional(args: Dict[str, Any], ctx: Dict[str, Any]) -> str:
    results = rs_adapter.download_traditional_archives(
        download_dir=Path(args["download_dir"]),
        seasons=args.get("seasons"),
        timeout=int(ctx.get("request_timeout_seconds", 120)),
        retries=int(ctx.get("retry_count", 3)),
        dry_run=ctx.get("dry_run", False),
    )
    ok = sum(1 for r in results if r["status"] in ("downloaded", "cached", "dry_run"))
    return f"{ok}/{len(results)} archives ok"


def retrosheet_extract_traditional(args: Dict[str, Any], ctx: Dict[str, Any]) -> str:
    results = rs_adapter.extract_traditional_archives(
        download_dir=Path(args["download_dir"]),
        extract_dir=Path(args["extract_dir"]),
        dry_run=ctx.get("dry_run", False),
    )
    ok = sum(1 for r in results if r["status"] in ("extracted", "dry_run"))
    return f"{ok}/{len(results)} archives extracted"


def retrosheet_download_csv(args: Dict[str, Any], ctx: Dict[str, Any]) -> str:
    results = rs_adapter.download_csv_bundles(
        download_dir=Path(args["download_dir"]),
        timeout=int(ctx.get("request_timeout_seconds", 120)),
        retries=int(ctx.get("retry_count", 3)),
        dry_run=ctx.get("dry_run", False),
    )
    ok = sum(1 for r in results if r["status"] in ("downloaded", "cached", "dry_run"))
    return f"{ok}/{len(results)} CSV bundles ok"


def chadwick_sync(args: Dict[str, Any], ctx: Dict[str, Any]) -> str:
    result = cw_adapter.sync_register(
        clone_dir=Path(args["clone_dir"]),
        git_bin=ctx.get("git_bin", "git"),
        dry_run=ctx.get("dry_run", False),
    )
    return result["status"]


def chadwick_copy_people(args: Dict[str, Any], ctx: Dict[str, Any]) -> str:
    results = cw_adapter.copy_people_files(
        clone_dir=Path(args["clone_dir"]),
        bronze_dir=Path(args["bronze_dir"]),
        dry_run=ctx.get("dry_run", False),
    )
    return f"copied {len(results)} people files"


def statcast_download_range(args: Dict[str, Any], ctx: Dict[str, Any]) -> str:
    results = sc_adapter.download_statcast_range(
        start=date.fromisoformat(args["start_date"]),
        end=date.fromisoformat(args["end_date"]),
        download_dir=Path(args["download_dir"]),
        chunk_days=int(args.get("chunk_days", 5)),
        dry_run=ctx.get("dry_run", False),
    )
    ok = sum(1 for r in results if r["status"] in ("downloaded", "cached", "dry_run"))
    return f"{ok}/{len(results)} chunks ok"


def ingest_directory_to_bronze(args: Dict[str, Any], ctx: Dict[str, Any]) -> str:
    dsn = ctx.get("postgres_dsn") or args["postgres_dsn"]
    results = bronze.ingest_directory_to_bronze(
        dsn=dsn,
        directory=Path(args["directory"]),
        schema_name=args["schema_name"],
        table_name=args["table_name"],
        source=args["source"],
        file_pattern=args.get("file_pattern", "*.csv"),
        dry_run=ctx.get("dry_run", False),
    )
    ok = sum(1 for r in results if r["status"] in ("ingested", "already_ingested", "dry_run"))
    return f"{ok}/{len(results)} files ingested"


ACTION_REGISTRY = {
    "ensure_directories":               ensure_directories,
    "log_message":                      log_message,
    "write_json":                       write_json,
    "retrosheet_download_traditional":  retrosheet_download_traditional,
    "retrosheet_extract_traditional":   retrosheet_extract_traditional,
    "retrosheet_download_csv":          retrosheet_download_csv,
    "chadwick_sync":                    chadwick_sync,
    "chadwick_copy_people":             chadwick_copy_people,
    "statcast_download_range":          statcast_download_range,
    "ingest_directory_to_bronze":       ingest_directory_to_bronze,
}
