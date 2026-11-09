"""Export US-located and US-remote jobs from a consistent database snapshot."""
import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scraper.us_locations import USLocations
from scraper.store import connect, FIELDS, write_json
from scraper.adapters import utcnow
from scraper.cli import safe_cell


def main():
    output = ROOT / "outputs" / "united_states"
    output.mkdir(parents=True, exist_ok=True)
    fields = [f for f in FIELDS if f != "description"] + ["country", "us_location_evidence"]
    db = connect(readonly=True)
    db.execute("BEGIN")
    locations = [r[0] for r in db.execute("SELECT DISTINCT location FROM jobs WHERE active=1 AND location IS NOT NULL")]
    classifier = USLocations(locations)
    rows = db.execute("SELECT * FROM jobs INDEXED BY jobs_company_title WHERE active=1 ORDER BY company COLLATE NOCASE,title COLLATE NOCASE,key")
    totals, excluded, companies, platforms = Counter(), Counter(), set(), Counter()
    target = output / "us_jobs.csv"
    temporary = target.with_suffix(".csv.tmp")
    with temporary.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            totals["scanned_jobs"] += 1
            match, reason = classifier.match(row["location"] or "")
            if not match:
                excluded[reason] += 1
                continue
            record = {field: safe_cell(row[field]) for field in fields if field in row.keys()}
            record.update(country="United States", us_location_evidence=reason)
            writer.writerow(record)
            totals["us_jobs"] += 1
            companies.add(row["company_key"])
            platforms[row["platform"]] += 1
    db.close()
    temporary.replace(target)
    summary = {"exported_at": utcnow(), **dict(totals), "company_feeds": len(companies), "platforms": dict(platforms),
        "exclusions": dict(excluded), "country": "United States",
        "policy": "US country labels, US city/state pairs validated against geodata and source locations explicitly labelled United States, unambiguous US state codes, US state names, and recognised/unambiguous US city labels. Generic/global remote, mixed-country locations, and unresolved locations excluded. Original location text retained.",
        "status": "Listed in source feed when checked_at; application pages not individually verified."}
    write_json(output / "us_jobs_summary.json", summary)
    print(json.dumps(summary, indent=2))
    print(target)


if __name__ == "__main__":
    main()
