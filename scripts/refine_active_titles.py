"""Exclude catch-all titles found during final review, without repeating HTTP checks."""
import csv
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scraper.availability import non_vacancy
from scripts.verify_active_jobs import SOURCE as ORIGINAL, Validator

OUT = ROOT / "outputs/united_states/active_only"
STATE = ROOT / "data/active_validation"


def main():
    old_summary = json.loads((OUT / "summary.json").read_text())
    manifest_path = OUT / "role_sheets/manifest.json"
    manifest = json.loads(manifest_path.read_text())
    baseline = {g["name"]: g["jobs"] for g in manifest["groups"]}
    (manifest_path.parent / "preview_baseline.json").write_text(json.dumps(baseline) + "\n")
    exclusions = []
    with (OUT / "active_us_jobs.csv").open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if non_vacancy(row["title"]):
                exclusions.append({"key": row["key"], "title": row["title"]})
    assert exclusions, "No additional titles need refinement"
    db = sqlite3.connect(STATE / "results.sqlite")
    reason = "Catch-all application, future-interest registration or recruitment event; not a specific current vacancy"
    for row in exclusions:
        cursor = db.execute("UPDATE checks SET status='excluded_general',reason=? WHERE key=? AND status='open'", (reason, row["key"]))
        assert cursor.rowcount == 1
    db.commit()
    db.close()
    with ORIGINAL.open(encoding="utf-8-sig", newline="") as handle:
        original_rows = list(csv.DictReader(handle))
    validator = Validator(original_rows, resume=True)
    assert validator.db.execute("SELECT COUNT(*) FROM checks").fetchone()[0] == len(original_rows)
    validator.progress("completed")
    validator.export()
    summary = json.loads((OUT / "summary.json").read_text())
    assert old_summary["active_jobs"] - summary["active_jobs"] == len(exclusions)
    # The creation marker already succeeded for this same workbook operation.
    marker_path = STATE / "delivery_artifact_marker.json"
    marker = json.loads(marker_path.read_text())
    marker["csv_sha256"] = summary["csv_sha256"]
    marker["revision_without_second_marker"] = True
    marker_path.write_text(json.dumps(marker) + "\n")
    (OUT / "title_review_exclusions.json").write_text(json.dumps(exclusions, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"additional_non_vacancies_excluded": len(exclusions), "active_jobs": summary["active_jobs"]}), flush=True)


if __name__ == "__main__":
    main()
