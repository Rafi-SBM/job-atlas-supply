"""Organize the delivered US-only CSV into role families, preserving every row."""
import csv
import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scraper.role_groups import classify_role
from scraper.store import write_json

SOURCE = ROOT / "outputs/united_states/us_jobs.csv"
OUT = ROOT / "outputs/united_states/role_sheets"


def main():
    global SOURCE, OUT
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    SOURCE, OUT = args.source.resolve(), args.output.resolve()
    groups, counts, fallback = defaultdict(list), Counter(), Counter()
    seen, source_keys = set(), []
    verified_from = verified_to = None
    with SOURCE.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames
        for row in reader:
            assert row["country"] == "United States"
            assert row["key"] not in seen
            seen.add(row["key"])
            source_keys.append(row["key"])
            name, method = classify_role(row["title"], row["department"])
            if "active_status" in row:
                assert row["active_status"] == "Open for applications when checked"
                assert row["active_verified_at"] and row["verification_evidence"]
                assert name != "General Applications"
                verified_from = min(verified_from or row["active_verified_at"], row["active_verified_at"])
                verified_to = max(verified_to or row["active_verified_at"], row["active_verified_at"])
            groups[name].append(row)
            counts[name] += 1
            fallback[method] += 1
    OUT.mkdir(parents=True, exist_ok=True)
    records = []
    for i, name in enumerate(sorted(groups)):
        rows = groups[name]
        rows.sort(key=lambda r: (r["title"].casefold(), r["company"].casefold(), r["location"].casefold(), r["key"]))
        filename = f"role-{i+1:02d}.json"
        write_json(OUT / filename, {"name": name, "fields": fields, "rows": rows})
        records.append({"name": name, "jobs": len(rows), "file": filename, "part": f"role-{i+1:02d}.xlsx"})
    total = sum(counts.values())
    assert total == len(seen)
    manifest = {"source": str(SOURCE), "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "total_jobs": total, "role_sheets": len(records), "fields": fields, "groups": records,
        "classification": dict(fallback), "verified_from": verified_from, "verified_to": verified_to,
        "policy": "Primary role family inferred from the original job title, with department as fallback. Each original US-only job appears once. Original titles and all source columns are retained."}
    write_json(OUT / "manifest.json", manifest)
    print(json.dumps({"jobs":total,"roles":len(records),"groups":dict(counts.most_common()),"classification":dict(fallback)},indent=2))
    other = Counter(r["title"] for r in groups.get("Other Roles", []))
    print("OTHER ROLE EXAMPLES", other.most_common(45))


if __name__ == "__main__":
    main()
