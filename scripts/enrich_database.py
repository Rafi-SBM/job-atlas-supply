#!/usr/bin/env python3
"""
Enrich data/jobs.sqlite with structured columns and composite indexes:
- role_group (31 career families)
- us_state (2-letter postal code, e.g. CA, NY, TX)
- us_city (normalized city name)
- is_us (1 for US-located / US-remote, 0 otherwise)
- active_status (open, unconfirmed, etc.)
- verification_evidence
- verified_at

Creates high-performance B-tree indexes for instant sub-20ms queries.
"""
import csv
import os
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scraper.role_groups import classify_role
from scraper.us_locations import USLocations, STATES

DB_PATH = ROOT / "data" / "jobs.sqlite"
ACTIVE_CSV = ROOT / "outputs" / "united_states" / "active_only" / "active_us_jobs.csv"


def extract_state_city(loc_classifier: USLocations, s: str):
    if not s:
        return "", ""
    s_clean = s.strip()
    m = loc_classifier.pair.search(s_clean)
    if m:
        c = m.group("city").strip().rstrip(",")
        st = m.group("state").strip().upper()
        code = STATES.get(st.casefold(), st if st in STATES.values() else "")
        return code, c
    m = loc_classifier.space_pair.match(s_clean)
    if m:
        c = m.group("city").strip()
        st = m.group("state").strip().upper()
        code = STATES.get(st.casefold(), st if st in STATES.values() else "")
        return code, c
    m = loc_classifier.full_state.search(s_clean.lower())
    if m:
        st_name = m.group(0)
        return STATES.get(st_name, ""), ""
    return "", ""


def main():
    if not DB_PATH.exists():
        print(f"Error: Database not found at {DB_PATH}")
        sys.exit(1)

    print(f"Connecting to database at {DB_PATH}...")
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA busy_timeout = 30000")

    # 1. Add columns if missing
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(jobs)")
    existing_cols = {row[1] for row in cursor.fetchall()}

    columns_to_add = [
        ("role_group", "TEXT DEFAULT ''"),
        ("us_state", "TEXT DEFAULT ''"),
        ("us_city", "TEXT DEFAULT ''"),
        ("is_us", "INTEGER DEFAULT 0"),
        ("active_status", "TEXT DEFAULT 'open'"),
        ("verification_evidence", "TEXT DEFAULT ''"),
        ("verified_at", "TEXT DEFAULT ''"),
    ]

    for col_name, col_def in columns_to_add:
        if col_name not in existing_cols:
            print(f"Adding column '{col_name}'...")
            conn.execute(f"ALTER TABLE jobs ADD COLUMN {col_name} {col_def}")
    conn.commit()

    loc_classifier = USLocations()

    # 2. Fast pass: populate from active_us_jobs.csv
    if ACTIVE_CSV.exists():
        print(f"Populating active verified US jobs from {ACTIVE_CSV}...")
        t0 = time.time()
        batch = []
        count = 0

        with open(ACTIVE_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                key = row.get("\ufeffkey") or row.get("key")
                if not key:
                    continue
                title = row.get("title", "")
                dept = row.get("department", "")
                loc_text = row.get("location", "")

                role, _ = classify_role(title, dept)
                st, city = extract_state_city(loc_classifier, loc_text)
                active_status = row.get("active_status", "open")
                evidence = row.get("verification_evidence", "")
                verified_at = row.get("active_verified_at", "")

                batch.append((role, st, city, 1, active_status, evidence, verified_at, key))
                count += 1

                if len(batch) >= 5000:
                    conn.executemany(
                        """UPDATE jobs SET 
                            role_group = ?,
                            us_state = ?,
                            us_city = ?,
                            is_us = ?,
                            active_status = ?,
                            verification_evidence = ?,
                            verified_at = ?
                        WHERE key = ?""",
                        batch
                    )
                    conn.commit()
                    batch = []
                    print(f"  Updated {count} verified US jobs...")

            if batch:
                conn.executemany(
                    """UPDATE jobs SET 
                        role_group = ?,
                        us_state = ?,
                        us_city = ?,
                        is_us = ?,
                        active_status = ?,
                        verification_evidence = ?,
                        verified_at = ?
                    WHERE key = ?""",
                    batch
                )
                conn.commit()

        print(f"Active US jobs pass finished: {count} rows updated in {time.time() - t0:.2f}s")

    # 3. Second pass: Classify remaining unclassified jobs
    print("Classifying remaining unclassified jobs in database...")
    t0 = time.time()
    unclassified = conn.execute(
        "SELECT key, title, department, location FROM jobs WHERE role_group = '' OR role_group IS NULL"
    ).fetchall()
    print(f"Found {len(unclassified)} unclassified jobs to process...")

    batch = []
    updated_remaining = 0
    for key, title, dept, loc_text in unclassified:
        role, _ = classify_role(title or "", dept or "")
        is_us = 0
        st, city = "", ""
        if loc_text:
            matched, _ = loc_classifier.match(loc_text)
            if matched:
                is_us = 1
                st, city = extract_state_city(loc_classifier, loc_text)

        batch.append((role, st, city, is_us, key))
        updated_remaining += 1

        if len(batch) >= 5000:
            conn.executemany(
                """UPDATE jobs SET 
                    role_group = ?,
                    us_state = ?,
                    us_city = ?,
                    is_us = ?
                WHERE key = ?""",
                batch
            )
            conn.commit()
            batch = []
            print(f"  Processed {updated_remaining} / {len(unclassified)}...")

    if batch:
        conn.executemany(
            """UPDATE jobs SET 
                role_group = ?,
                us_state = ?,
                us_city = ?,
                is_us = ?
            WHERE key = ?""",
            batch
        )
        conn.commit()
    print(f"Remaining jobs pass finished in {time.time() - t0:.2f}s")

    # 4. Create composite performance indexes
    print("Building composite performance indexes...")
    t0 = time.time()
    indexes = [
        ("idx_jobs_filter", "jobs(active, is_us, us_state, role_group)"),
        ("idx_jobs_role", "jobs(active, role_group)"),
        ("idx_jobs_state", "jobs(active, us_state)"),
        ("idx_jobs_us", "jobs(active, is_us)"),
        ("idx_jobs_active_status", "jobs(active, active_status)"),
    ]

    for idx_name, idx_def in indexes:
        print(f"  Creating index {idx_name}...")
        conn.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {idx_def}")

    conn.commit()
    print(f"All indexes created in {time.time() - t0:.2f}s")

    # 5. Write precomputed metadata cache
    print("Writing data/metadata.json precomputed cache...")
    roles = [{'name': r[0], 'jobs': r[1]} for r in conn.execute("SELECT role_group, COUNT(*) FROM jobs WHERE active=1 AND role_group != '' GROUP BY role_group ORDER BY COUNT(*) DESC").fetchall()]
    states = [{'state': r[0], 'jobs': r[1]} for r in conn.execute("SELECT us_state, COUNT(*) FROM jobs WHERE active=1 AND is_us=1 AND us_state != '' GROUP BY us_state ORDER BY COUNT(*) DESC").fetchall()]
    platforms = [{'platform': r[0], 'jobs': r[1], 'companies': r[2]} for r in conn.execute("SELECT platform, COUNT(*), COUNT(DISTINCT company_key) FROM jobs INDEXED BY jobs_summary WHERE active=1 GROUP BY platform ORDER BY COUNT(*) DESC").fetchall()]
    total = conn.execute("SELECT COUNT(*) FROM jobs WHERE active=1").fetchone()[0]
    us_total = conn.execute("SELECT COUNT(*) FROM jobs WHERE active=1 AND is_us=1").fetchone()[0]
    us_remote = conn.execute("SELECT COUNT(*) FROM jobs WHERE active=1 AND is_us=1 AND workplace='Remote'").fetchone()[0]
    checked_at = conn.execute("SELECT MAX(checked_at) FROM jobs WHERE active=1").fetchone()[0]

    meta = {
        'role_groups': roles,
        'states': states,
        'platforms': platforms,
        'total_jobs': total,
        'total_us_jobs': us_total,
        'total_us_remote': us_remote,
        'checked_at': checked_at
    }
    with open(ROOT / "data" / "metadata.json", "w") as f:
        json.dump(meta, f, indent=2)
    print("  Successfully generated data/metadata.json")

    # 6. Quick verification query & speed benchmark
    print("\n--- Verification Benchmarks ---")
    t0 = time.time()
    sample = conn.execute(
        """SELECT role_group, COUNT(*) as cnt 
        FROM jobs 
        WHERE active = 1 AND is_us = 1 
        GROUP BY role_group 
        ORDER BY cnt DESC 
        LIMIT 5"""
    ).fetchall()
    elapsed = time.time() - t0
    print(f"Top 5 US Role Groups (Query executed in {elapsed*1000:.2f}ms):")
    for role, cnt in sample:
        print(f"  • {role}: {cnt:,} jobs")

    t0 = time.time()
    state_sample = conn.execute(
        """SELECT us_state, COUNT(*) as cnt 
        FROM jobs 
        WHERE active = 1 AND is_us = 1 AND us_state != '' 
        GROUP BY us_state 
        ORDER BY cnt DESC 
        LIMIT 5"""
    ).fetchall()
    elapsed = time.time() - t0
    print(f"\nTop 5 US States (Query executed in {elapsed*1000:.2f}ms):")
    for st, cnt in state_sample:
        print(f"  • {st}: {cnt:,} jobs")

    conn.close()
    print("\nEnrichment complete! Database is ready for sub-20ms queries.")


if __name__ == "__main__":
    main()

