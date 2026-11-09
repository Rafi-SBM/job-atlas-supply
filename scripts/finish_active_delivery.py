"""Finish the requested role workbook and company CSV folder after validation."""
from __future__ import annotations
import csv
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "data/active_validation"
OUT = ROOT / "outputs/united_states/active_only"
SOURCE = OUT / "active_us_jobs.csv"
RUNTIME = Path("/Users/rafi/.cache/codex-runtimes/codex-primary-runtime/dependencies")
NODE = RUNTIME / "node/bin/node"
PYTHON = RUNTIME / "python/bin/python3"
MARKER = Path("/Users/rafi/.codex/plugins/cache/openai-primary-runtime/spreadsheets/26.1026.10807/skills/spreadsheets/container_tools/mark_artifact_operation_started.mjs")


def phase(value, **extra):
    report = {"phase": value, "updated_at": datetime.now(timezone.utc).isoformat(), **extra}
    path = STATE / "delivery_progress.json"
    temp = path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(report, indent=2) + "\n")
    temp.replace(path)
    print(json.dumps(report), flush=True)


def run(args):
    subprocess.run([str(v) for v in args], cwd=ROOT, check=True)


def audit():
    summary = json.loads((OUT / "summary.json").read_text())
    progress = json.loads((STATE / "progress.json").read_text())
    assert progress["status"] == "completed" and progress["remaining"] == 0
    assert summary["exported_at"] >= progress["updated_at"]
    with SOURCE.open("rb") as handle:
        fingerprint = hashlib.file_digest(handle, "sha256").hexdigest()
    assert fingerprint == summary["csv_sha256"]
    db = sqlite3.connect((STATE / "results.sqlite").resolve().as_uri() + "?mode=ro", uri=True)
    counts = dict(db.execute("SELECT status,COUNT(*) FROM checks GROUP BY status"))
    assert counts == progress["results"]
    assert sum(counts.values()) == summary["candidates"] == 171002
    checks = {row[0]: row[1:] for row in db.execute("SELECT key,verified_at,reason,url,http_status FROM checks WHERE status='open'")}
    db.close()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=6)
    seen = set()
    with SOURCE.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            key = row["key"]
            assert key not in seen and key in checks
            when, reason, url, code = checks[key]
            assert code == 200
            assert row["active_status"] == "Open for applications when checked"
            assert row["country"] == "United States"
            assert row["active_verified_at"] == when
            assert row["verification_evidence"] == reason
            assert row["verification_url"] == url
            assert datetime.fromisoformat(when.replace("Z", "+00:00")) >= cutoff
            seen.add(key)
    assert seen == set(checks)
    assert len(seen) == summary["active_jobs"]
    return {"active_jobs": len(seen), "all_candidates_checked": True, "positive_http_application_evidence": True,
            "all_checks_within_six_hours": True, "csv_sha256": fingerprint, "excluded": counts}


def main():
    phase("waiting_for_application_checks")
    while True:
        progress = json.loads((STATE / "progress.json").read_text())
        if progress["status"] == "completed" and (OUT / "summary.json").exists():
            summary = json.loads((OUT / "summary.json").read_text())
            if summary["exported_at"] >= progress["updated_at"]:
                break
        pid = int((STATE / "validator.pid").read_text())
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            raise RuntimeError("Application validator stopped before completing the export")
        time.sleep(15)
    phase("checking_filtered_export")
    report = audit()
    (OUT / "active_only_audit.json").write_text(json.dumps(report, indent=2) + "\n")
    folder = OUT / "role_sheets"
    phase("grouping_active_jobs_by_role", jobs=report["active_jobs"])
    run([PYTHON, ROOT / "scripts/prepare_role_sheets.py", "--source", SOURCE, "--output", folder])
    marker_state = STATE / "delivery_artifact_marker.json"
    saved_marker = json.loads(marker_state.read_text()) if marker_state.exists() else {}
    if saved_marker.get("csv_sha256") != report["csv_sha256"]:
        run([NODE, MARKER, "--operation-kind", "create", "--expected-output-count", "1", "--output-format", "xlsx"])
        marker_state.write_text(json.dumps({"csv_sha256": report["csv_sha256"]}) + "\n")
    phase("writing_and_verifying_role_workbook", jobs=report["active_jobs"])
    workbook = OUT / "active_us_jobs_by_role.xlsx"
    run([PYTHON, ROOT / "scripts/build_role_workbook.py", "--folder", folder, "--output", workbook])
    phase("rendering_role_sheet_previews")
    run([NODE, ROOT / "workbook/roles.mjs", "--folder", folder, "--reuse-unchanged"])
    phase("writing_company_csv_files")
    run([PYTHON, ROOT / "scripts/export_company_csvs.py"])
    companies = json.loads((OUT / "companies_manifest.json").read_text())
    assert companies["jobs"] == report["active_jobs"]
    phase("ready_for_visual_review", jobs=report["active_jobs"],
          role_workbook=str(workbook), company_csv_files=companies["company_csv_files"],
          companies_folder=str(ROOT / "companies"), zip=str(OUT / "companies.zip"))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        phase("failed", error=f"{type(exc).__name__}: {exc}")
        raise
