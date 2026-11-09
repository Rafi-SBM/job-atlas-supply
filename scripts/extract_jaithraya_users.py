#!/usr/bin/env python3
"""
Extract all candidate users and their pull filters from Jaithraya PostgreSQL DB.
Strictly READ-ONLY pass over the database.
"""

import json
import os
import re
import sys
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor

DB_URL = "postgresql://job_discovery_db_rotated_20260616_user:pzR9SzsCT9d230uXIoiferXtFitfHp8O@dpg-d88eletckfvc73fj10t0-a.oregon-postgres.render.com/job_discovery_db_j3f3?sslmode=require"

US_STATES = {
    'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas', 'CA': 'California',
    'CO': 'Colorado', 'CT': 'Connecticut', 'DE': 'Delaware', 'FL': 'Florida', 'GA': 'Georgia',
    'HI': 'Hawaii', 'ID': 'Idaho', 'IL': 'Illinois', 'IN': 'Indiana', 'IA': 'Iowa',
    'KS': 'Kansas', 'KY': 'Kentucky', 'LA': 'Louisiana', 'ME': 'Maine', 'MD': 'Maryland',
    'MA': 'Massachusetts', 'MI': 'Michigan', 'MN': 'Minnesota', 'MS': 'Mississippi', 'MO': 'Missouri',
    'MT': 'Montana', 'NE': 'Nebraska', 'NV': 'Nevada', 'NH': 'New Hampshire', 'NJ': 'New Jersey',
    'NM': 'New Mexico', 'NY': 'New York', 'NC': 'North Carolina', 'ND': 'North Dakota', 'OH': 'Ohio',
    'OK': 'Oklahoma', 'OR': 'Oregon', 'PA': 'Pennsylvania', 'RI': 'Rhode Island', 'SC': 'South Carolina',
    'SD': 'South Dakota', 'TN': 'Tennessee', 'TX': 'Texas', 'UT': 'Utah', 'VT': 'Vermont',
    'VA': 'Virginia', 'WA': 'Washington', 'WV': 'West Virginia', 'WI': 'Wisconsin', 'WY': 'Wyoming',
    'DC': 'District of Columbia'
}
STATE_NAME_TO_CODE = {v.lower(): k for k, v in US_STATES.items()}

def parse_states_from_locations(locations):
    states = set()
    for loc in locations or []:
        if not loc:
            continue
        # Check standard 2-letter code e.g. ", CA", "CA, United States", etc.
        m = re.findall(r'\b([A-Z]{2})\b', loc)
        for code in m:
            if code in US_STATES:
                states.add(code)
        # Check state full name
        loc_lower = loc.lower()
        for name, code in STATE_NAME_TO_CODE.items():
            if name in loc_lower:
                states.add(code)
    return sorted(list(states))

def main():
    print("Connecting to Jaithraya database in READ-ONLY mode...")
    conn = psycopg2.connect(DB_URL, connect_timeout=15)
    conn.set_session(readonly=True)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    print("Fetching candidate profiles...")
    cur.execute("""
        SELECT 
            candidate_id, handle, name, target_titles, skills, locations, 
            remote_preference, employment_types, excluded_companies, min_salary_usd, 
            seniority_levels, is_active, job_supply_enabled, daily_application_target,
            role_cluster_preferences, work_authorization_status, requires_sponsorship_now,
            created_at, updated_at
        FROM candidate_profiles
        ORDER BY job_supply_enabled DESC, is_active DESC, handle ASC;
    """)
    profiles = cur.fetchall()
    print(f"Loaded {len(profiles)} total candidate profiles.")

    print("Fetching UIP resolver outputs...")
    cur.execute("""
        SELECT candidate_id, cluster_key, resolver_output
        FROM candidate_uips;
    """)
    uips = {row["candidate_id"]: row for row in cur.fetchall()}

    print("Fetching approved role tracks...")
    cur.execute("""
        SELECT candidate_id, role_family, display_title, titles, supporting_skills, status
        FROM candidate_role_tracks
        WHERE status IN ('APPROVED', 'PROPOSED');
    """)
    role_tracks_by_candidate = {}
    for row in cur.fetchall():
        cid = row["candidate_id"]
        role_tracks_by_candidate.setdefault(cid, []).append(row)

    print("Fetching master CV self-employers...")
    cur.execute("""
        SELECT m.candidate_id, b.employer
        FROM master_cv_bullets b
        JOIN master_cvs m ON b.master_cv_id = m.master_cv_id
        WHERE b.employer IS NOT NULL AND b.employer != ''
        GROUP BY m.candidate_id, b.employer;
    """)
    employers_by_candidate = {}
    for row in cur.fetchall():
        cid = row["candidate_id"]
        emp = row["employer"].strip()
        if emp:
            employers_by_candidate.setdefault(cid, set()).add(emp)

    print("Fetching 60-day company cooldown histories...")
    cur.execute("""
        SELECT s.candidate_id, j.company_name
        FROM candidate_daily_shortlist_items si
        JOIN candidate_daily_shortlists s ON si.shortlist_id = s.shortlist_id
        JOIN jobs j ON si.job_id = j.job_id
        WHERE s.shortlist_date >= NOW() - INTERVAL '60 days'
          AND j.company_name IS NOT NULL AND j.company_name != ''
        GROUP BY s.candidate_id, j.company_name;
    """)
    cooldowns_by_candidate = {}
    for row in cur.fetchall():
        cid = row["candidate_id"]
        cname = row["company_name"].strip()
        if cname:
            cooldowns_by_candidate.setdefault(cid, set()).add(cname)

    # Operator submissions (done-for-you applications)
    cur.execute("""
        SELECT sub.candidate_id, j.company_name
        FROM operator_submissions sub
        JOIN jobs j ON sub.job_id = j.job_id
        WHERE sub.reversed_at IS NULL
          AND sub.submitted_at >= NOW() - INTERVAL '60 days'
          AND j.company_name IS NOT NULL AND j.company_name != ''
        GROUP BY sub.candidate_id, j.company_name;
    """)
    for row in cur.fetchall():
        cid = row["candidate_id"]
        cname = row["company_name"].strip()
        if cname:
            cooldowns_by_candidate.setdefault(cid, set()).add(cname)

    cur.close()
    conn.close()

    candidates_out = []
    for p in profiles:
        cid = p["candidate_id"]
        uip_data = uips.get(cid)
        resolver_out = uip_data.get("resolver_output", {}) if uip_data else {}
        uip_spec = resolver_out.get("uip", {}) if isinstance(resolver_out, dict) else {}

        parsed_states = parse_states_from_locations(p["locations"])

        self_employers = sorted(list(employers_by_candidate.get(cid, set())))
        cooldown_companies = sorted(list(cooldowns_by_candidate.get(cid, set())))
        explicit_excluded = p["excluded_companies"] or []

        all_excluded_companies = sorted(list(set(self_employers + cooldown_companies + explicit_excluded)))

        # Aggregate titles
        all_titles = []
        if p["target_titles"]:
            all_titles.extend(p["target_titles"])
        if uip_spec.get("targetTitles"):
            all_titles.extend(uip_spec["targetTitles"])
        tracks = role_tracks_by_candidate.get(cid, [])
        for t in tracks:
            if t.get("titles"):
                all_titles.extend(t["titles"])
        # Deduplicate preserving order
        seen_titles = set()
        clean_titles = []
        for title in all_titles:
            norm = title.strip()
            if norm and norm.lower() not in seen_titles:
                seen_titles.add(norm.lower())
                clean_titles.append(norm)

        # Candidate record
        record = {
            "candidate_id": cid,
            "handle": p["handle"],
            "name": p["name"],
            "is_active": p["is_active"],
            "job_supply_enabled": p["job_supply_enabled"],
            "daily_application_target": p["daily_application_target"] or 30,
            "remote_preference": p["remote_preference"],
            "locations": p["locations"] or [],
            "target_us_states": parsed_states,
            "primary_role_family": uip_spec.get("primaryRoleFamily") or (tracks[0]["role_family"] if tracks else None),
            "role_families": resolver_out.get("roleFamilies") or [t["role_family"] for t in tracks],
            "target_titles": clean_titles,
            "skills": p["skills"] or resolver_out.get("coreSkills") or [],
            "seniority_levels": p["seniority_levels"] or uip_spec.get("seniorityBands") or [],
            "min_salary_usd": p["min_salary_usd"],
            "work_authorization": {
                "status": p["work_authorization_status"],
                "requires_sponsorship_now": p["requires_sponsorship_now"],
            },
            "filters": {
                "titles": clean_titles[:15],
                "states": parsed_states,
                "remote_preference": p["remote_preference"],
                "exclude_companies_count": len(all_excluded_companies),
                "cooldown_companies_count": len(cooldown_companies),
                "self_employers_count": len(self_employers),
            },
            "cooldown_companies_sample": cooldown_companies[:20],
            "self_employers": self_employers,
            "all_excluded_companies": all_excluded_companies
        }
        candidates_out.append(record)

    output_path = os.path.join(os.path.dirname(__file__), "..", "data", "jaithraya_users.json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "extracted_at": datetime.utcnow().isoformat() + "Z",
            "total_candidates": len(candidates_out),
            "supply_enabled_candidates": sum(1 for c in candidates_out if c["job_supply_enabled"]),
            "active_candidates": sum(1 for c in candidates_out if c["is_active"]),
            "candidates": candidates_out
        }, f, indent=2)

    print(f"SUCCESS: Saved {len(candidates_out)} users to {output_path}")

if __name__ == "__main__":
    main()

