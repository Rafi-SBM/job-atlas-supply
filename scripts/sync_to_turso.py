#!/usr/bin/env python3
"""
Sync active verified US jobs to Turso Cloud Database (libSQL).
Turso Free Tier: 5 GB storage, 500 million reads/month, $0.00 cost forever.

Uses Turso's /v2/pipeline HTTP API with standard Python libraries (no pip dependencies required).
"""
import csv
import json
import os
import sqlite3
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "jobs.sqlite"
ACTIVE_CSV = ROOT / "outputs" / "united_states" / "active_only" / "active_us_jobs.csv"


def get_turso_credentials():
    url = os.environ.get("TURSO_DATABASE_URL", "").strip()
    token = os.environ.get("TURSO_AUTH_TOKEN", "").strip()

    if not url or not token:
        # Check .env file
        env_file = ROOT / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("TURSO_DATABASE_URL="):
                    url = line.split("=", 1)[1].strip().strip('"').strip("'")
                elif line.startswith("TURSO_AUTH_TOKEN="):
                    token = line.split("=", 1)[1].strip().strip('"').strip("'")

    if not url:
        print("ERROR: TURSO_DATABASE_URL is not set.")
        print("To create a free Turso database:")
        print("  1. Run: brew install tursodatabase/tap/turso")
        print("  2. Run: turso auth signup (or login)")
        print("  3. Run: turso db create job-atlas-us")
        print("  4. Run: turso db show job-atlas-us --url")
        print("  5. Run: turso db tokens create job-atlas-us")
        print("  6. Set TURSO_DATABASE_URL and TURSO_AUTH_TOKEN in .env")
        sys.exit(1)

    # Convert libsql:// or https:// to https pipeline URL
    clean_url = url.replace("libsql://", "https://")
    if not clean_url.endswith("/v2/pipeline"):
        clean_url = clean_url.rstrip("/") + "/v2/pipeline"

    return clean_url, token


def execute_pipeline(pipeline_url: str, token: str, statements: list):
    requests = []
    for stmt in statements:
        if isinstance(stmt, str):
            requests.append({"type": "execute", "stmt": {"sql": stmt}})
        elif isinstance(stmt, dict):
            requests.append({"type": "execute", "stmt": stmt})

    payload = json.dumps({"requests": requests}).encode("utf-8")
    req = urllib.request.Request(
        pipeline_url,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        method="POST"
    )

    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    pipeline_url, token = get_turso_credentials()
    print(f"Connecting to Turso pipeline at {pipeline_url}...")

    # Test connection
    try:
        res = execute_pipeline(pipeline_url, token, ["SELECT 1 as ping"])
        print("Turso connection test successful!")
    except Exception as e:
        print(f"Connection failed: {e}")
        sys.exit(1)

    # 1. Initialize schema
    print("Creating schema on Turso Cloud...")
    create_schema_stmts = [
        """CREATE TABLE IF NOT EXISTS jobs (
            key TEXT PRIMARY KEY,
            company TEXT,
            company_key TEXT,
            platform TEXT,
            board TEXT,
            job_id TEXT,
            title TEXT,
            location TEXT,
            workplace TEXT,
            department TEXT,
            employment_type TEXT,
            published_at TEXT,
            updated_at TEXT,
            checked_at TEXT,
            salary_min REAL,
            salary_max REAL,
            salary_currency TEXT,
            salary_interval TEXT,
            salary_text TEXT,
            url TEXT,
            apply_url TEXT,
            source_url TEXT,
            date_note TEXT,
            role_group TEXT,
            us_state TEXT,
            us_city TEXT,
            is_us INTEGER DEFAULT 1,
            active INTEGER DEFAULT 1,
            active_status TEXT DEFAULT 'open',
            verification_evidence TEXT,
            verified_at TEXT
        )""",
        "CREATE INDEX IF NOT EXISTS idx_turso_filter ON jobs(active, is_us, us_state, role_group)",
        "CREATE INDEX IF NOT EXISTS idx_turso_role ON jobs(active, role_group)",
        "CREATE INDEX IF NOT EXISTS idx_turso_state ON jobs(active, us_state)",
        "CREATE INDEX IF NOT EXISTS idx_turso_remote ON jobs(active, is_us, workplace)"
    ]
    execute_pipeline(pipeline_url, token, create_schema_stmts)
    print("Schema and indexes initialized on Turso.")

    # 2. Sync from local SQLite
    if not DB_PATH.exists():
        print(f"Local database not found at {DB_PATH}")
        sys.exit(1)

    local_conn = sqlite3.connect(str(DB_PATH))
    cursor = local_conn.cursor()

    total_us = cursor.execute("SELECT COUNT(*) FROM jobs WHERE is_us = 1").fetchone()[0]
    print(f"Found {total_us:,} active US jobs to sync...")

    query = """SELECT 
        key, company, company_key, platform, board, job_id, title, location,
        workplace, department, employment_type, published_at, updated_at, checked_at,
        salary_min, salary_max, salary_currency, salary_interval, salary_text,
        url, apply_url, source_url, date_note, role_group, us_state, us_city,
        is_us, active, active_status, verification_evidence, verified_at
    FROM jobs 
    WHERE is_us = 1"""

    cursor.execute(query)

    batch_size = 100
    batch = []
    synced = 0
    t0 = time.time()

    cols = """key, company, company_key, platform, board, job_id, title, location,
    workplace, department, employment_type, published_at, updated_at, checked_at,
    salary_min, salary_max, salary_currency, salary_interval, salary_text,
    url, apply_url, source_url, date_note, role_group, us_state, us_city,
    is_us, active, active_status, verification_evidence, verified_at"""
    placeholders = ",".join(["?" for _ in range(31)])

    while True:
        rows = cursor.fetchmany(batch_size)
        if not rows:
            break

        statements = []
        for r in rows:
            # Construct parameterized libSQL statement
            params = [
                {"type": "null"} if v is None else
                {"type": "integer", "value": str(v)} if isinstance(v, int) else
                {"type": "float", "value": v} if isinstance(v, float) else
                {"type": "text", "value": str(v)}
                for v in r
            ]
            statements.append({
                "sql": f"INSERT OR REPLACE INTO jobs ({cols}) VALUES ({placeholders})",
                "args": params
            })

        execute_pipeline(pipeline_url, token, statements)
        synced += len(rows)
        if synced % 1000 == 0:
            print(f"  Synced {synced:,} / {total_us:,} jobs ({time.time() - t0:.1f}s)...")

    local_conn.close()
    print(f"\nSuccessfully synced {synced:,} jobs to Turso Cloud in {time.time() - t0:.2f}s!")


if __name__ == "__main__":
    main()
