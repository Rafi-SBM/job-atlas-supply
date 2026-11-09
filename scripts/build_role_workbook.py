"""Stream the delivered US snapshot into a single role-grouped workbook.

The normal Artifact Tool exporter exceeded its available heap on large sheets.
Use the bundled openpyxl write-only exporter for the full dataset; retain the
Artifact-generated previews for visual review.
"""
import csv
import argparse
import hashlib
import json
import math
from datetime import datetime, timezone, timedelta
from pathlib import Path
from zipfile import ZipFile

from openpyxl import Workbook, load_workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Alignment, Font, NamedStyle, PatternFill
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "outputs/united_states/role_sheets"
OUTPUT = FOLDER.parent / "us_jobs_by_role.xlsx"
COLUMNS = [
    ("title", "Job title", 74), ("company", "Company", 36),
    ("location", "Location", 52), ("workplace", "Work arrangement", 20),
    ("employment_type", "Employment type", 22), ("department", "Department", 36),
    ("salary_min", "Salary minimum", 18), ("salary_max", "Salary maximum", 18),
    ("salary_currency", "Currency", 13), ("salary_interval", "Pay interval", 20),
    ("salary_text", "Compensation supplied by source", 60),
    ("published_at", "Published at", 23), ("updated_at", "Updated at", 23),
    ("checked_at", "Checked at (UTC)", 23), ("url", "Employer job URL", 80),
    ("apply_url", "Application URL", 80), ("source_url", "Source feed URL", 80),
    ("country", "Country", 20), ("us_location_evidence", "US location evidence", 46),
    ("date_note", "Source date or coverage note", 85), ("platform", "Platform", 20),
    ("board", "Board identifier", 44), ("job_id", "Job ID", 44),
    ("company_key", "Company key", 50), ("key", "Unique posting key", 75),
]
DATES = {"published_at", "updated_at", "checked_at"}
NUMBERS = {"salary_min", "salary_max"}
ACTIVE_COLUMNS = [
    ("active_status", "Application status", 42),
    ("active_verified_at", "Applications verified at (UTC)", 28),
    ("verification_method", "Verification method", 60),
    ("verification_url", "Live verification URL", 90),
    ("verification_evidence", "Evidence of application availability", 100),
]


def converted(value, key):
    if value in ("", None):
        return None
    if key in DATES:
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if value.tzinfo:
                value = value.astimezone(timezone.utc).replace(tzinfo=None)
            # XLSX date values have millisecond precision.
            return value.replace(microsecond=0) + timedelta(milliseconds=round(value.microsecond / 1000))
        except ValueError:
            pass
    elif key in NUMBERS:
        try:
            number = float(value)
            if math.isfinite(number):
                return number
        except ValueError:
            pass
    assert len(str(value)) <= 32767, f"Excel text limit exceeded in {key}"
    return str(value)


def add_styles(wb):
    for name, fill, wrap, bold, size, color, fmt, horizontal in [
        ("body", None, False, False, 10, "27372D", "General", "left"),
        ("wrapped", None, True, False, 10, "27372D", "General", "left"),
        ("number", None, False, False, 10, "27372D", "#,##0.00", "right"),
        ("date", None, False, False, 10, "27372D", "dd mmm yyyy hh:mm", "left"),
        ("header", "203E32", True, True, 10, "FFFFFF", "General", "center"),
        ("title", None, False, True, 16, "203E32", "General", "left"),
        ("note", None, False, False, 10, "738365", "General", "left"),
        ("count", None, False, False, 10, "27372D", "#,##0", "right"),
        ("percent", None, False, False, 10, "27372D", "0.0%", "right"),
        ("link", None, False, False, 10, "236451", "General", "left"),
    ]:
        style = NamedStyle(name=name)
        style.font = Font(name="Arial", size=size, bold=bold, color=color,
                          underline="single" if name == "link" else None)
        style.alignment = Alignment(vertical="center", horizontal=horizontal, wrap_text=wrap)
        style.number_format = fmt
        if fill:
            style.fill = PatternFill("solid", fgColor=fill)
        wb.add_named_style(style)


def cell(ws, value, style="body", link=None):
    c = WriteOnlyCell(ws, value=value)
    if isinstance(value, str):
        c.data_type = "s"  # Keep source text literal, including formula-like titles.
    c.style = style
    if link:
        c.hyperlink = link
    return c


def create_index(wb, manifest):
    active = "active_status" in manifest["fields"]
    ws = wb.create_sheet("Index")
    ws.sheet_view.showGridLines = False
    ws.sheet_properties.tabColor = "203E32"
    for col, width in [("A", 46), ("B", 18), ("C", 20)]:
        ws.column_dimensions[col].width = width
    ws.sheet_format.defaultRowHeight = 26
    ws.freeze_panes = "A8"
    ws.auto_filter.ref = f"A7:C{7 + len(manifest['groups'])}"
    if active and manifest.get("verified_from"):
        start = datetime.fromisoformat(manifest["verified_from"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(manifest["verified_to"].replace("Z", "+00:00"))
        label = "Application checks: " + start.strftime("%d %b %Y, %H:%M") + " to " + end.strftime("%H:%M UTC" if start.date() == end.date() else "%d %b %Y, %H:%M UTC")
    else:
        label = None
    ws.append([])
    ws.row_dimensions[2].height = 30
    ws.append([cell(ws, "Active US jobs by role" if active else "US jobs by role", "title")])
    ws.append([cell(ws, "Original titles retained. One primary role family per job.", "note")])
    ws.append([cell(ws, "Application-verified US jobs" if active else "Total US jobs"), cell(ws, manifest["total_jobs"], "count")])
    ws.append([cell(ws, label, "note")] if label else [])
    ws.append([cell(ws, "Grouping uses job titles, with department as fallback.", "note")])
    ws.row_dimensions[7].height = 30
    ws.append([cell(ws, h, "header") for h in ["Role family", "Jobs", "Share of jobs"]])
    for group in manifest["groups"]:
        target = "#'" + group["name"].replace("'", "''") + "'!A1"
        ws.append([cell(ws, group["name"], "link", target),
                   cell(ws, group["jobs"], "count"),
                   cell(ws, group["jobs"] / manifest["total_jobs"], "percent")])
    ws.append([])
    for note in [
        f"{manifest['total_jobs']:,} US jobs with positive application availability checks." if active else f"All {manifest['total_jobs']:,} records are from the delivered United States snapshot.",
        f"Every job appears once. All {len(COLUMNS)} source and verification columns are retained on each role sheet.",
        "Other Roles contains jobs without a clear title or department match.",
        "Use the filters in row 5 of each role sheet to narrow the listings.",
        "Dates reflect the source; blank dates were not supplied. Times are in UTC.",
        "Each listing retains its employer URL, application URL and source feed URL.",
        f"Source: {Path(manifest['source']).name} · {manifest['total_jobs']:,} US listings.",
    ]:
        ws.append([cell(ws, note, "note")])
    if active:
        for note in [
            "General applications, talent pools, expired, closed and unconfirmed postings are excluded.",
            "Verification checks the exact job's live application form, application schema or canApply status.",
            "Each role sheet records the check time, verification URL and evidence for every job.",
            "No applications were submitted. Availability reflects the time of each check.",
        ]:
            ws.append([cell(ws, note, "note")])


def create_role(wb, group):
    data = json.loads((FOLDER / group["file"]).read_text())
    assert len(data["rows"]) == group["jobs"]
    ws = wb.create_sheet(group["name"])
    assert len(ws.title) <= 31
    ws.sheet_view.showGridLines = False
    ws.sheet_properties.tabColor = "738365"
    ws.sheet_format.defaultRowHeight = 32
    ws.freeze_panes = "C6"
    ws.auto_filter.ref = f"A5:{get_column_letter(len(COLUMNS))}{5 + group['jobs']}"
    for i, (_, _, width) in enumerate(COLUMNS, 1):
        ws.column_dimensions[get_column_letter(i)].width = width
    ws.append([])
    ws.row_dimensions[2].height = 30
    ws.append([cell(ws, group["name"], "title"), None, None, None, None, None,
               cell(ws, "Back to index", "link", "#'Index'!A1")])
    ws.row_dimensions[3].height = 20
    ws.append([cell(ws, f"{group['jobs']:,} US jobs · sorted by title and company", "note")])
    ws.append([])
    ws.row_dimensions[5].height = 36
    ws.append([cell(ws, label, "header") for _, label, _ in COLUMNS])
    for n, row in enumerate(data["rows"], 6):
        lines = max(math.ceil(len(row[k]) / width) for k, width in [
            ("title", 90), ("company", 40), ("location", 58), ("department", 42)])
        if lines > 2:
            ws.row_dimensions[n].height = min(409, lines * 15 + 6)
        values = []
        for i, (key, _, _) in enumerate(COLUMNS):
            value = converted(row[key], key)
            style = "date" if isinstance(value, datetime) else (
                "number" if key in NUMBERS else "wrapped" if i < 6 or key == "verification_evidence" else "body")
            values.append(cell(ws, value, style))
        ws.append(values)
    print(f"Wrote {group['name']}: {group['jobs']:,} jobs", flush=True)


def verify(path, manifest):
    with ZipFile(path) as archive:
        assert archive.testzip() is None
        from xml.etree import ElementTree as ET
        ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        for i, group in enumerate(manifest["groups"], 2):
            xml = ET.parse(archive.open(f"xl/worksheets/sheet{i}.xml"))
            assert xml.find("s:autoFilter", ns).get("ref") == f"A5:{get_column_letter(len(COLUMNS))}{5 + group['jobs']}"
            assert xml.find("s:sheetViews/s:sheetView/s:pane", ns).get("topLeftCell") == "C6"
            assert xml.find(".//s:f", ns) is None
    print("Workbook file structure and filters verified.", flush=True)
    wb = load_workbook(path, read_only=True, data_only=False)
    assert wb.sheetnames == ["Index"] + [g["name"] for g in manifest["groups"]]
    assert wb["Index"]["B4"].value == manifest["total_jobs"]
    seen = set()
    for group in manifest["groups"]:
        source = json.loads((FOLDER / group["file"]).read_text())["rows"]
        ws = wb[group["name"]]
        rows = ws.iter_rows(min_row=5, max_col=len(COLUMNS), values_only=True)
        assert next(rows) == tuple(label for _, label, _ in COLUMNS)
        count = 0
        for row, original in zip(rows, source, strict=True):
            expected = tuple(converted(original[key], key) for key, _, _ in COLUMNS)
            assert row == expected, f"Field mismatch in {group['name']}: {original['key']}"
            assert row[17] == "United States"
            if "active_status" in manifest["fields"]:
                assert original["active_status"] == "Open for applications when checked"
                assert original["active_verified_at"] and original["verification_evidence"]
            assert row[-1] not in seen
            seen.add(row[-1])
            count += 1
        assert count == group["jobs"]
        print(f"Verified {group['name']}: {count:,} complete records", flush=True)
    wb.close()
    source = Path(manifest["source"])
    assert hashlib.sha256(source.read_bytes()).hexdigest() == manifest["source_sha256"]
    with source.open(encoding="utf-8-sig", newline="") as handle:
        source_keys = {r["key"] for r in csv.DictReader(handle)}
    assert seen == source_keys
    assert len(seen) == manifest["total_jobs"]
    report = {"file": str(OUTPUT), "jobs": len(seen), "worksheets": len(wb.sheetnames),
              "role_sheets": len(manifest["groups"]), "all_source_fields_matched": True,
              "every_job_once": True, "country": "United States",
              "source_sha256": manifest["source_sha256"], "zip_verified": True,
              "verified_at": datetime.now(timezone.utc).isoformat()}
    return report


def main():
    global FOLDER, OUTPUT, COLUMNS
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder", type=Path, default=FOLDER)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    FOLDER, OUTPUT = args.folder.resolve(), args.output.resolve()
    manifest = json.loads((FOLDER / "manifest.json").read_text())
    if "active_status" in manifest["fields"]:
        COLUMNS = COLUMNS[:-1] + ACTIVE_COLUMNS + COLUMNS[-1:]
        DATES.add("active_verified_at")
    assert {key for key, _, _ in COLUMNS} == set(manifest["fields"])
    assert sum(g["jobs"] for g in manifest["groups"]) == manifest["total_jobs"]
    wb = Workbook(write_only=True)
    wb.properties.title = "United States jobs by role"
    wb.properties.subject = "Delivered US-only job listings grouped into primary role families"
    wb.properties.creator = "Job Atlas"
    add_styles(wb)
    create_index(wb, manifest)
    for group in manifest["groups"]:
        create_role(wb, group)
    temporary = OUTPUT.with_suffix(".tmp.xlsx")
    wb.save(temporary)
    print(f"Saved {temporary.stat().st_size / 1024**2:.1f} MB; checking every field…", flush=True)
    report = verify(temporary, manifest)
    temporary.replace(OUTPUT)
    (FOLDER / "verification.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
