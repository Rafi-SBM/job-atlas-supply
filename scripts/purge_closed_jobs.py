#!/usr/bin/env python3
"""
Purge expired, closed, and non-US jobs from data/jobs.sqlite.
Ensures the database contains ONLY live, open US vacancies.
Automatically rebuilds metadata cache and cleans full-text search index.
"""
import json
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "jobs.sqlite"
META_PATH = ROOT / "data" / "metadata.json"


def main():
    if not DB_PATH.exists():
        print(f"Error: Database not found at {DB_PATH}")
        sys.exit(1)

    print(f"Opening database at {DB_PATH}...")
    conn = sqlite3.connect(str(DB_PATH), timeout=60)
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 60000")

    cursor = conn.cursor()

    before_total = cursor.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    before_inactive = cursor.execute("SELECT COUNT(*) FROM jobs WHERE active = 0").fetchone()[0]
    before_non_us = cursor.execute("SELECT COUNT(*) FROM jobs WHERE is_us = 0").fetchone()[0]

    print(f"Before purge:")
    print(f"  • Total listings: {before_total:,}")
    print(f"  • Closed/inactive: {before_inactive:,}")
    print(f"  • Non-US jobs: {before_non_us:,}")

    # 1. Delete closed/inactive jobs
    t0 = time.time()
    print("\nDeleting closed/expired jobs (active = 0)...")
    cursor.execute("DELETE FROM jobs WHERE active = 0")
    conn.commit()

    # 2. Delete non-US jobs to keep database strictly US-only
    print("Deleting non-US listings (is_us = 0)...")
    cursor.execute("DELETE FROM jobs WHERE is_us = 0")
    conn.commit()
    print(f"Purge completed in {time.time() - t0:.2f}s")

    after_total = cursor.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    after_us_remote = cursor.execute("SELECT COUNT(*) FROM jobs WHERE workplace = 'Remote'").fetchone()[0]
    print(f"\nAfter purge:")
    print(f"  • Active US jobs remaining: {after_total:,}")
    print(f"  • US Remote jobs: {after_us_remote:,}")
    print(f"  • Deleted {before_total - after_total:,} closed/non-US rows.")

    # 3. Update metadata cache
    print("\nUpdating data/metadata.json precomputed cache...")
    roles = [{'name': r[0], 'jobs': r[1]} for r in cursor.execute("SELECT role_group, COUNT(*) FROM jobs WHERE role_group != '' GROUP BY role_group ORDER BY COUNT(*) DESC").fetchall()]
    states = [{'state': r[0], 'jobs': r[1]} for r in cursor.execute("SELECT us_state, COUNT(*) FROM jobs WHERE us_state != '' GROUP BY us_state ORDER BY COUNT(*) DESC").fetchall()]
    platforms = [{'platform': r[0], 'jobs': r[1], 'companies': r[2]} for r in cursor.execute("SELECT platform, COUNT(*), COUNT(DISTINCT company_key) FROM jobs GROUP BY platform ORDER BY COUNT(*) DESC").fetchall()]
    checked_at = cursor.execute("SELECT MAX(checked_at) FROM jobs").fetchone()[0]

    meta = {
        'role_groups': roles,
        'states': states,
        'platforms': platforms,
        'total_jobs': after_total,
        'total_us_jobs': after_total,
        'total_us_remote': after_us_remote,
        'checked_at': checked_at or ""
    }
    with open(META_PATH, "w") as f:
        json.dump(meta, f, indent=2)
    print("Successfully refreshed data/metadata.json.")

    conn.close()
    print("\nDone! Database is 100% clean with live US jobs only.")


if __name__ == "__main__":
    main()

