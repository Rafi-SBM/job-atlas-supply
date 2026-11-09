"""Reconcile every company sheet and package the Excel volumes."""
import csv
import io
import json
import os
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(os.environ.get("JOB_ATLAS_EXPORT_DIR", str(ROOT / "outputs" / "job-atlas")))
FOLDER = OUT / "workbooks"
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def main():
    manifest = json.loads((OUT / "manifest.json").read_text())
    expected = {c["company_key"]: c for c in manifest["companies"]}
    index = json.loads((FOLDER / "workbook-index.json").read_text())
    parts = {}
    for record in index:
        if record["company_key"] not in expected or record["jobs"] != expected[record["company_key"]]["jobs"]:
            raise RuntimeError(f"Outdated workbook: {record['workbook']}")
        parts.setdefault(record["workbook"], []).append(record)
    keys = [r["company_key"] for r in index]
    if len(keys) != len(set(keys)) or set(keys) != set(expected):
        raise RuntimeError(f"Company coverage mismatch: {len(set(keys))}/{len(expected)}")
    if sum(r["jobs"] for r in index) != manifest["total_jobs"]:
        raise RuntimeError("Workbook counts do not match the combined CSV manifest")
    for filename, records in parts.items():
        with zipfile.ZipFile(FOLDER / filename) as xlsx:
            if xlsx.testzip() is not None:
                raise RuntimeError(f"Invalid XLSX ZIP: {filename}")
            book = ET.fromstring(xlsx.read("xl/workbook.xml"))
            sheet_names = [e.attrib["name"] for e in book.findall("m:sheets/m:sheet", NS)]
            if sheet_names != ["Index"] + [r["sheet"] for r in records]:
                raise RuntimeError(f"Sheet names do not reconcile: {filename}")
            for i, record in enumerate(records, start=2):
                with xlsx.open(f"xl/worksheets/sheet{i}.xml") as xml:
                    row_count = 0
                    for _event, element in ET.iterparse(xml, events=("end",)):
                        if element.tag.endswith("}row"):
                            if int(element.attrib.get("r", 0)) >= 6:
                                row_count += 1
                            element.clear()
                    if row_count != record["jobs"]:
                        raise RuntimeError(f"Missing job rows in {filename}/{record['sheet']}: {row_count}/{record['jobs']}")
        print(f"Verified {filename}: {len(records)} company sheets", flush=True)
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=["company", "company_key", "platform", "jobs", "workbook", "sheet"])
    writer.writeheader()
    writer.writerows(index)
    (FOLDER / "workbook-index.csv").write_text("\ufeff" + buffer.getvalue(), encoding="utf-8")
    (FOLDER / "workbook-index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    readme = f"""Job Atlas — company worksheets

Snapshot exported: {manifest['exported_at']}
Listed jobs: {manifest['total_jobs']:,}
Company feeds: {manifest['total_companies']:,}
Excel volumes: {len(parts)}

Open workbook-index.csv to find a company's workbook and sheet name.
Each volume includes its own Index and one worksheet per company feed.
Company keys are platform:tenant. Employers on separate platforms are not guessed/merged.

Listed means present in an employer's feed or sitemap at checked_at.
Application pages have not all been individually tested. Missing data stays blank.
Greenhouse updated_at is a modification time; Workday relative dates remain in date_note.
Full available descriptions are stored in the local SQLite database, not these workbooks.
Original job links, source URLs, check times and compensation supplied by the source are retained.

Sources:
https://github.com/strelov1/freehire
https://github.com/Riley-Dorrington/job-board-aggregator
https://github.com/mherzog4/job-boards

Riley-Dorrington's company lists are CC BY-NC 4.0. This derived collection is for
noncommercial use. Original postings remain their owners' content.
"""
    (FOLDER / "README.txt").write_text(readme, encoding="utf-8")
    target = OUT / "company_workbooks.zip"
    temporary = target.with_suffix(".zip.tmp")
    with zipfile.ZipFile(temporary, "w", zipfile.ZIP_STORED, allowZip64=True) as archive:
        for filename in parts:
            archive.write(FOLDER / filename, filename)
        archive.write(FOLDER / "workbook-index.csv", "workbook-index.csv")
        archive.writestr("README.txt", readme)
    temporary.replace(target)
    report = {"jobs": manifest["total_jobs"], "companies": len(index), "volumes": len(parts), "archive_bytes": target.stat().st_size, "all_sheet_names_and_row_counts_verified": True}
    (OUT / "verification.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
