#!/usr/bin/env python3
"""
Test all Jaithraya users' filters against the current Job Atlas pool (data/jobs.sqlite).
Calculates exact match yield, unique company inventory, cooldown compliance,
and daily quota viability for each candidate.
"""

import json
import os
import sqlite3
import re
from datetime import datetime

ATLAS_DB = os.path.join(os.path.dirname(__file__), "..", "data", "jobs.sqlite")
USERS_JSON = os.path.join(os.path.dirname(__file__), "..", "data", "jaithraya_users.json")

# Map Jaithraya role families to Job Atlas 31 standardized role_groups
ROLE_FAMILY_MAP = {
    "software-engineer": "Software Engineering",
    "full-stack-developer": "Software Engineering",
    "backend-developer": "Software Engineering",
    "frontend-developer": "Software Engineering",
    "java-developer": "Software Engineering",
    "python-developer": "Software Engineering",
    "application-developer": "Software Engineering",
    "data-analyst": "Data and AI",
    "data-engineer": "Data and AI",
    "data-scientist": "Data and AI",
    "machine-learning-engineer": "Data and AI",
    "ai-ml-engineer": "Data and AI",
    "ai-engineer": "Data and AI",
    "business-intelligence": "Data and AI",
    "cloud-engineer": "Software Engineering",
    "devops-engineer": "Software Engineering",
    "platform-engineer": "Software Engineering",
    "site-reliability-engineer": "Software Engineering",
    "cybersecurity": "Software Engineering",
    "security-engineer": "Software Engineering",
    "qa-engineer": "Software Engineering",
    "test-engineer": "Software Engineering",
    "business-analyst": "Business Operations",
    "product-manager": "Product Management",
    "technical-product-manager": "Product Management",
    "project-manager": "Projects and Programs",
    "program-manager": "Projects and Programs",
    "scrum-master": "Projects and Programs",
    "financial-analyst": "Finance and Accounting",
    "accountant": "Finance and Accounting",
    "application-support": "Software Engineering",
    "application-support-analyst": "Software Engineering",
    "mainframe-developer": "Software Engineering",
    "cloud-network-engineer": "Hardware and Engineering",
    "security-analyst": "Software Engineering",
    "qa-analyst": "Software Engineering",
}

def clean_company_name(name: str) -> str:
    """Normalize company name for fuzzy/case-insensitive cooldown comparison."""
    if not name:
        return ""
    # Strip common suffixes and punctuation
    cleaned = re.sub(r'(?i)\b(inc|llc|corp|ltd|co|corporation|technologies|solutions|group|holdings)\b', '', name)
    cleaned = re.sub(r'[^a-zA-Z0-9]', '', cleaned)
    return cleaned.lower().strip()

def run_simulation():
    if not os.path.exists(ATLAS_DB):
        print(f"Error: Database {ATLAS_DB} not found!")
        return
    if not os.path.exists(USERS_JSON):
        print(f"Error: {USERS_JSON} not found!")
        return

    with open(USERS_JSON) as f:
        user_data = json.load(f)

    candidates = user_data["candidates"]
    conn = sqlite3.connect(ATLAS_DB)
    cur = conn.cursor()

    print(f"Loaded {len(candidates)} candidates from Jaithraya.")
    print("Testing candidate filters against Job Atlas SQLite pool...")
    print("=" * 80)

    results = []
    
    # Process all supply-enabled candidates first, then other active candidates
    candidates_to_test = [c for c in candidates if c["job_supply_enabled"]]
    if len(candidates_to_test) < 20:
        candidates_to_test += [c for c in candidates if c["is_active"] and not c["job_supply_enabled"]]

    for cand in candidates_to_test:
        cid = cand["candidate_id"]
        handle = cand["handle"]
        name = cand["name"]
        supply_enabled = cand["job_supply_enabled"]
        daily_target = cand["daily_application_target"] or 30
        primary_family = cand["primary_role_family"] or ""
        role_group = ROLE_FAMILY_MAP.get(primary_family)
        target_titles = cand["target_titles"][:6]
        states = cand["target_us_states"]
        remote_pref = cand["remote_preference"]
        excluded_companies = cand["all_excluded_companies"]

        # Build clean excluded company set
        excluded_norm = {clean_company_name(c) for c in excluded_companies if clean_company_name(c)}

        # Build SQL Query
        where_clauses = ["is_us = 1", "active = 1"]
        params = []

        # Role filter
        if role_group:
            where_clauses.append("role_group = ?")
            params.append(role_group)
        elif target_titles:
            title_conditions = []
            for t in target_titles:
                title_conditions.append("title LIKE ?")
                params.append(f"%{t}%")
            where_clauses.append(f"({' OR '.join(title_conditions)})")

        # Location filter
        is_nationwide = any("united states" in loc.lower() or "remote (us)" in loc.lower() for loc in cand["locations"])
        if remote_pref == "REMOTE_ONLY":
            where_clauses.append("(workplace = 'Remote' OR location LIKE '%Remote%')")
        elif states and not is_nationwide:
            placeholders = ",".join(["?"] * len(states))
            if remote_pref == "REMOTE_OK":
                where_clauses.append(f"(us_state IN ({placeholders}) OR workplace = 'Remote' OR location LIKE '%Remote%')")
            else:
                where_clauses.append(f"us_state IN ({placeholders})")
            params.extend(states)
        elif remote_pref == "REMOTE_OK" and not states:
            # Nationwide + Remote
            pass

        # Execute candidate raw matching query
        sql = f"""
            SELECT key, title, company, company_key, us_state, us_city, workplace, role_group, apply_url, published_at
            FROM jobs
            WHERE {' AND '.join(where_clauses)}
            ORDER BY COALESCE(NULLIF(published_at, ''), checked_at) DESC
        """
        cur.execute(sql, params)
        raw_matches = cur.fetchall()

        # Apply Cooldown and Distinct-Company in-memory
        unique_companies_seen = set()
        cooldown_dropped = 0
        eligible_jobs = []

        for row in raw_matches:
            cname = row[2] or ""
            norm_c = clean_company_name(cname)

            # Check 60-day cooldown / explicit exclusions
            if norm_c in excluded_norm:
                cooldown_dropped += 1
                continue

            # Check distinct company per daily batch
            ckey = row[3] or norm_c
            if ckey in unique_companies_seen:
                continue

            unique_companies_seen.add(ckey)
            eligible_jobs.append({
                "key": row[0],
                "title": row[1],
                "company": cname,
                "location": f"{row[5]}, {row[4]}" if row[4] else "US",
                "workplace": row[6],
                "role_group": row[7],
                "apply_url": row[8],
                "published_at": row[9]
            })

        can_fulfill_quota = len(eligible_jobs) >= daily_target
        days_of_runway = round(len(eligible_jobs) / daily_target, 1)

        summary_entry = {
            "handle": handle,
            "name": name,
            "supply_enabled": supply_enabled,
            "daily_target": daily_target,
            "role_family": primary_family,
            "atlas_role_group": role_group or "Title-based fallback",
            "remote_preference": remote_pref,
            "target_states": states,
            "cooldown_companies_history": cand["filters"]["cooldown_companies_count"] if isinstance(cand["filters"]["cooldown_companies_count"], int) else len(cand["filters"]["cooldown_companies_count"]),
            "raw_atlas_matching_jobs": len(raw_matches),
            "cooldown_dropped_jobs": cooldown_dropped,
            "eligible_unique_companies": len(eligible_jobs),
            "can_fulfill_daily_quota": can_fulfill_quota,
            "days_of_supply_runway": days_of_runway,
            "sample_top_deliverable_jobs": eligible_jobs[:3]
        }
        results.append(summary_entry)

    # Output detailed report
    print(f"\n{'HANDLE':<32} | {'ROLE':<20} | {'RAW MATCH':<10} | {'COOLDOWN DROPPED':<16} | {'ELIGIBLE COS':<12} | {'QUOTA (30)':<10} | {'RUNWAY'}")
    print("-" * 120)
    for r in results[:20]:
        quota_str = "PASSED" if r["can_fulfill_daily_quota"] else "SHORT"
        print(f"{r['handle']:<32} | {r['role_family']:<20} | {r['raw_atlas_matching_jobs']:<10,} | {r['cooldown_dropped_jobs']:<16,} | {r['eligible_unique_companies']:<12,} | {quota_str:<10} | {r['days_of_supply_runway']} days")

    # Aggregate metrics
    total_tested = len(results)
    passed_quota = sum(1 for r in results if r["can_fulfill_daily_quota"])
    avg_runway = sum(r["days_of_supply_runway"] for r in results) / total_tested if total_tested else 0

    print("=" * 120)
    print(f"Summary Audit Across {total_tested} Candidates:")
    print(f"  • Daily Quota Attainment (>= {30} unique companies today): {passed_quota}/{total_tested} ({passed_quota/total_tested*100:.1f}%)")
    print(f"  • Average Supply Runway without repeating companies: {avg_runway:.1f} days")

    # Save simulation results
    report_path = os.path.join(os.path.dirname(__file__), "..", "data", "atlas_candidate_simulation_results.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({
            "tested_at": datetime.utcnow().isoformat() + "Z",
            "candidates_tested": total_tested,
            "passed_quota_count": passed_quota,
            "pass_rate_pct": round(passed_quota / total_tested * 100, 1),
            "average_runway_days": round(avg_runway, 1),
            "candidate_results": results
        }, f, indent=2)

    print(f"Saved full simulation report to {report_path}")

    conn.close()

if __name__ == "__main__":
    run_simulation()
