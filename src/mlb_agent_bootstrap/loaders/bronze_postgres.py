"""
Bronze Postgres loader.
Loads raw CSVs and Parquet files into bronze schemas in Postgres.
Preserves all columns. Records checksums, row counts, and ingest status
in bronze_meta.ingest_manifest. Never silently drops data.
"""
from __future__ import annotations

import hashlib
import io
from pathlib import Path
from typing import Any, Dict, List

import psycopg2
import psycopg2.extras


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _ensure_manifest_table(conn: Any) -> None:
    with conn.cursor() as cur:
        cur.execute("""
            CREATE SCHEMA IF NOT EXISTS bronze_meta;
            CREATE TABLE IF NOT EXISTS bronze_meta.ingest_manifest (
                id            BIGSERIAL PRIMARY KEY,
                source        TEXT NOT NULL,
                file_path     TEXT NOT NULL,
                file_sha256   TEXT NOT NULL,
                schema_name   TEXT NOT NULL,
                table_name    TEXT NOT NULL,
                row_count     BIGINT,
                ingested_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                status        TEXT NOT NULL,
                detail        TEXT
            );
        """)
    conn.commit()


def _record_manifest(conn, source, file_path, sha256, schema_name, table_name, row_count, status, detail=""):
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO bronze_meta.ingest_manifest
              (source,file_path,file_sha256,schema_name,table_name,row_count,status,detail)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (source, file_path, sha256, schema_name, table_name, row_count, status, detail))
    conn.commit()


def _already_ingested(conn, sha256: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM bronze_meta.ingest_manifest WHERE file_sha256=%s AND status='success'",
            (sha256,)
        )
        return cur.fetchone() is not None


def ingest_csv_to_bronze(
    dsn: str, csv_path: Path, schema_name: str, table_name: str,
    source: str, dry_run: bool = False,
) -> Dict[str, Any]:
    import pandas as pd
    sha = _sha256(csv_path)
    df = pd.read_csv(csv_path, low_memory=False, dtype=str)
    row_count = len(df)
    if dry_run:
        return {"file": csv_path.name, "status": "dry_run", "rows": row_count}
    conn = psycopg2.connect(dsn)
    try:
        _ensure_manifest_table(conn)
        if _already_ingested(conn, sha):
            return {"file": csv_path.name, "status": "already_ingested", "sha256": sha}
        cols_ddl = ", ".join(f'"{c}" TEXT' for c in df.columns)
        with conn.cursor() as cur:
            cur.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_name}")
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {schema_name}.{table_name} (
                    _ingest_id   BIGSERIAL,
                    _source_file TEXT,
                    _ingested_at TIMESTAMPTZ DEFAULT NOW(),
                    {cols_ddl}
                )
            """)
        conn.commit()
        buf = io.StringIO()
        df.to_csv(buf, index=False)
        buf.seek(0)
        cols = ", ".join(f'"{c}"' for c in df.columns)
        with conn.cursor() as cur:
            cur.copy_expert(
                f"COPY {schema_name}.{table_name} ({cols}) FROM STDIN WITH (FORMAT CSV, HEADER TRUE)",
                buf
            )
        conn.commit()
        _record_manifest(conn, source, str(csv_path), sha, schema_name, table_name, row_count, "success")
        return {"file": csv_path.name, "status": "ingested", "rows": row_count, "sha256": sha}
    except Exception as exc:
        conn.rollback()
        try:
            _record_manifest(conn, source, str(csv_path), sha, schema_name, table_name, 0, "failed", str(exc))
        except Exception:
            pass
        raise
    finally:
        conn.close()


def ingest_parquet_to_bronze(
    dsn: str, parquet_path: Path, schema_name: str, table_name: str,
    source: str, dry_run: bool = False,
) -> Dict[str, Any]:
    import pandas as pd
    sha = _sha256(parquet_path)
    df = pd.read_parquet(parquet_path)
    df = df.astype(str).replace("nan", None).replace("<NA>", None)
    row_count = len(df)
    if dry_run:
        return {"file": parquet_path.name, "status": "dry_run", "rows": row_count}
    conn = psycopg2.connect(dsn)
    try:
        _ensure_manifest_table(conn)
        if _already_ingested(conn, sha):
            return {"file": parquet_path.name, "status": "already_ingested", "sha256": sha}
        cols_ddl = ", ".join(f'"{c}" TEXT' for c in df.columns)
        with conn.cursor() as cur:
            cur.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_name}")
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {schema_name}.{table_name} (
                    _ingest_id   BIGSERIAL,
                    _source_file TEXT,
                    _ingested_at TIMESTAMPTZ DEFAULT NOW(),
                    {cols_ddl}
                )
            """)
        conn.commit()
        rows = [[parquet_path.name] + [row[c] for c in df.columns] for _, row in df.iterrows()]
        cols_insert = "_source_file, " + ", ".join(f'"{c}"' for c in df.columns)
        placeholders = ", ".join(["%s"] * (len(df.columns) + 1))
        with conn.cursor() as cur:
            psycopg2.extras.execute_batch(
                cur,
                f"INSERT INTO {schema_name}.{table_name} ({cols_insert}) VALUES ({placeholders})",
                rows, page_size=500,
            )
        conn.commit()
        _record_manifest(conn, source, str(parquet_path), sha, schema_name, table_name, row_count, "success")
        return {"file": parquet_path.name, "status": "ingested", "rows": row_count, "sha256": sha}
    except Exception as exc:
        conn.rollback()
        try:
            _record_manifest(conn, source, str(parquet_path), sha, schema_name, table_name, 0, "failed", str(exc))
        except Exception:
            pass
        raise
    finally:
        conn.close()


def ingest_directory_to_bronze(
    dsn: str, directory: Path, schema_name: str, table_name: str,
    source: str, file_pattern: str = "*.csv", dry_run: bool = False,
) -> List[Dict[str, Any]]:
    is_parquet = file_pattern.endswith(".parquet")
    loader = ingest_parquet_to_bronze if is_parquet else ingest_csv_to_bronze
    return [loader(dsn, fp, schema_name, table_name, source, dry_run=dry_run)
            for fp in sorted(directory.glob(file_pattern))]
