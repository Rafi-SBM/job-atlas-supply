"""Partition the completed, application-verified US export by company.

Write rows incrementally so thousands of company files do not need thousands
of open file handles or copies of the full dataset in memory.
"""
from __future__ import annotations
import csv
import hashlib
import json
import re
import sys
import unicodedata
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "outputs/united_states/active_only/active_us_jobs.csv"
DELIVERY = SOURCE.parent
DESTINATION = ROOT / "companies"


def company_id(value):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value)).strip().casefold()


def filename(value, identifier, used):
    ascii_name = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    base = re.sub(r"[^a-zA-Z0-9._-]+", "_", ascii_name).strip("._-")[:110] or "company"
    if base.upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}:
        base = "company_" + base
    candidate = base + ".csv"
    if candidate.casefold() in used:
        candidate = base + "__" + hashlib.sha256(identifier.encode()).hexdigest()[:10] + ".csv"
    assert candidate.casefold() not in used
    used.add(candidate.casefold())
    return candidate


def row_hash(row):
    return hashlib.sha256(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).digest()


def main():
    progress = json.loads((ROOT / "data/active_validation/progress.json").read_text())
    summary = json.loads((DELIVERY / "summary.json").read_text())
    assert progress["status"] == "completed" and progress["remaining"] == 0
    assert summary["exported_at"] >= progress["updated_at"], "The filtered export is from an earlier validation run"
    with SOURCE.open("rb") as source_handle:
        source_hash = hashlib.file_digest(source_handle, "sha256").hexdigest()
    assert source_hash == summary["csv_sha256"]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    stage = ROOT / (".companies_build_" + stamp)
    stage.mkdir()
    groups, handles, used, expected = {}, OrderedDict(), set(), {}
    try:
        with SOURCE.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fields = reader.fieldnames
            for row in reader:
                assert row["active_status"] == "Open for applications when checked"
                assert row["country"] == "United States"
                assert row["active_verified_at"] and row["verification_evidence"]
                key = row["key"]
                assert key not in expected
                expected[key] = row_hash(row)
                identifier = company_id(row["company"])
                assert identifier
                if identifier not in groups:
                    groups[identifier] = {"company": row["company"], "file": filename(row["company"], identifier, used),
                                          "jobs": 0, "platforms": set(), "company_keys": set(),
                                          "verified_from": row["active_verified_at"], "verified_to": row["active_verified_at"]}
                group = groups[identifier]
                group["jobs"] += 1
                group["platforms"].add(row["platform"])
                group["company_keys"].add(row["company_key"])
                group["verified_from"] = min(group["verified_from"], row["active_verified_at"])
                group["verified_to"] = max(group["verified_to"], row["active_verified_at"])
                if identifier in handles:
                    output, writer = handles.pop(identifier)
                else:
                    if len(handles) >= 96:
                        _, (old_handle, _) = handles.popitem(last=False)
                        old_handle.close()
                    path = stage / group["file"]
                    exists = path.exists()
                    output = path.open("a" if exists else "w", encoding="utf-8" if exists else "utf-8-sig", newline="")
                    writer = csv.DictWriter(output, fieldnames=fields)
                    if not exists:
                        writer.writeheader()
                writer.writerow(row)
                handles[identifier] = output, writer
    finally:
        for handle, _ in handles.values():
            handle.close()
    assert len(expected) == summary["active_jobs"]
    print(f"Wrote {len(groups):,} company CSV files. Checking every exported field…", flush=True)
    seen = set()
    for identifier, group in groups.items():
        count = 0
        with (stage / group["file"]).open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            assert reader.fieldnames == fields
            for row in reader:
                key = row["key"]
                assert key not in seen
                assert company_id(row["company"]) == identifier
                assert expected[key] == row_hash(row)
                assert row["active_status"] == "Open for applications when checked"
                seen.add(key)
                count += 1
        assert count == group["jobs"]
    assert seen == set(expected)
    assert len(list(stage.glob("*.csv"))) == len(groups)
    records = []
    for group in sorted(groups.values(), key=lambda x: x["company"].casefold()):
        group["platforms"] = sorted(group["platforms"])
        group["company_keys"] = sorted(group["company_keys"])
        records.append(group)
    manifest = {"source": str(SOURCE), "source_sha256": source_hash, "country": "United States",
                "jobs": len(seen), "company_csv_files": len(records), "fields": fields,
                "verified_from": min(g["verified_from"] for g in records),
                "verified_to": max(g["verified_to"] for g in records),
                "grouping": "Company names match after Unicode, whitespace and case normalization; no guessed company mergers.",
                "all_fields_verified": True, "every_job_once": True, "companies": records}
    (stage / ".export_info.json").write_text(json.dumps({k: v for k, v in manifest.items() if k != "companies"}, indent=2) + "\n")
    if DESTINATION.exists():
        previous = ROOT / ("companies_previous_" + stamp)
        DESTINATION.rename(previous)
        print(f"Preserved the previous folder at {previous}", flush=True)
    stage.rename(DESTINATION)
    index = DELIVERY / "companies_index.csv"
    with index.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["company", "csv_file", "active_jobs", "platforms", "verified_from_utc", "verified_to_utc"])
        for group in records:
            writer.writerow([group["company"], group["file"], group["jobs"], "; ".join(group["platforms"]), group["verified_from"], group["verified_to"]])
    (DELIVERY / "companies_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    archive = DELIVERY / "companies.zip"
    temporary = archive.with_suffix(".tmp.zip")
    with ZipFile(temporary, "w", ZIP_DEFLATED, compresslevel=6) as zipped:
        for group in records:
            zipped.write(DESTINATION / group["file"], "companies/" + group["file"])
        zipped.write(index, "companies_index.csv")
    with ZipFile(temporary) as zipped:
        assert zipped.testzip() is None
        assert len(zipped.namelist()) == len(records) + 1
    temporary.replace(archive)
    print(json.dumps({"folder": str(DESTINATION), "company_csv_files": len(records),
                      "active_us_jobs": len(seen), "all_fields_verified": True,
                      "archive": str(archive)}, indent=2), flush=True)


if __name__ == "__main__":
    main()
