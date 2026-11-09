from __future__ import annotations

import argparse
import csv
import io
import hashlib
import json
import os
import re
import signal
import sqlite3
import sys
import time
import zipfile
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from datetime import datetime, timezone
from pathlib import Path

from .adapters import fetch_board, utcnow, STOP_EVENT
from .registry import build_registry, PLATFORMS
from .store import ROOT, FIELDS, connect, persist_board, write_json

OUTPUT = ROOT / "outputs" / "job-atlas"


def load_env():
    path = ROOT / ".env"
    if path.exists():
        for line in path.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip("\"'"))


def scrape(args):
    load_env()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", os.environ.get("JOB_SCRAPER_CONTACT", "")):
        raise SystemExit("Set JOB_SCRAPER_CONTACT to a real contact email in .env before scraping.")
    db = connect()
    lock = ROOT / "data" / "scrape.lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
    except FileExistsError:
        try:
            pid = int(lock.read_text())
            os.kill(pid, 0)
        except (ProcessLookupError, ValueError):
            lock.unlink(missing_ok=True)
            return scrape(args)
        raise SystemExit("A scraper is already running. Watch data/progress.json or the local dashboard.")
    try:
        return run_scrape(args, db)
    finally:
        lock.unlink(missing_ok=True)
        db.close()


def run_scrape(args, db):
    STOP_EVENT.clear()
    registry = build_registry()
    platforms = args.platforms.split(",") if args.platforms else list(PLATFORMS)
    if any(p not in PLATFORMS for p in platforms):
        raise SystemExit(f"Valid platforms: {', '.join(PLATFORMS)}")
    registry = [b for b in registry if b["platform"] in platforms]
    # Cover the low-request-cost platforms first. Workday requires pagination.
    order = {p: i for i, p in enumerate(["greenhouse", "ashby", "lever", "workable", "recruitee", "smartrecruiters", "personio", "breezy", "bamboohr", "icims", "paylocity", "workday"])}
    registry.sort(key=lambda b: order[b["platform"]])
    if args.board:
        registry = [b for b in registry if b["board"].lower() == args.board.lower()]
    if args.limit:
        # A small smoke run samples each selected platform rather than only one.
        buckets = defaultdict(list)
        for b in registry:
            buckets[b["platform"]].append(b)
        sampled = []
        while len(sampled) < args.limit and any(buckets.values()):
            for bucket in buckets.values():
                if bucket and len(sampled) < args.limit:
                    sampled.append(bucket.pop(0))
        registry = sampled
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    previous = db.execute("SELECT * FROM runs WHERE status IN ('running','interrupted') ORDER BY started_at DESC LIMIT 1").fetchone() if args.resume else None
    done = set()
    if previous:
        run_id = previous["id"]
        done = {(r[0], r[1]) for r in db.execute("SELECT platform,board FROM boards WHERE run_id=? AND status IN ('ok','not_found')", (run_id,))}
    started = previous["started_at"] if previous else utcnow()
    db.execute("INSERT OR REPLACE INTO runs(id,started_at,status,total_boards,completed_boards,jobs,platforms,errors) VALUES(?,?,?,?,?,?,?,?)",
        (run_id, started, "running", len(registry), len(done), 0, json.dumps(platforms), 0))
    db.commit()
    pending = [b for b in registry if (b["platform"], b["board"]) not in done]
    completed = len(done)
    counts = Counter()
    stop = False

    def interrupt(_sig, _frame):
        nonlocal stop
        stop = True
        STOP_EVENT.set()
        print("Stopping after in-flight boards. Progress is saved; use --resume.", flush=True)

    signal.signal(signal.SIGINT, interrupt)
    signal.signal(signal.SIGTERM, interrupt)
    begin = time.monotonic()

    def progress(status="running"):
        live = db.execute("SELECT COUNT(*) FROM jobs WHERE active=1").fetchone()[0]
        companies = db.execute("SELECT COUNT(DISTINCT company_key) FROM jobs WHERE active=1").fetchone()[0]
        stats = [dict(r) for r in db.execute("SELECT platform,COUNT(*) jobs,COUNT(DISTINCT company_key) companies FROM jobs WHERE active=1 GROUP BY platform ORDER BY jobs DESC")]
        errors = db.execute("SELECT COUNT(*) FROM boards WHERE run_id=? AND status NOT IN ('ok','not_found')", (run_id,)).fetchone()[0]
        db.execute("UPDATE runs SET status=?,completed_boards=?,jobs=?,errors=? WHERE id=?", (status, completed, live, errors, run_id))
        db.commit()
        value = {"run_id": run_id, "status": status, "started_at": started, "updated_at": utcnow(),
            "completed_boards": completed, "total_boards": len(registry), "jobs": live, "companies": companies,
            "errors": errors, "elapsed_seconds": round(time.monotonic() - begin), "platforms": stats,
            "board_statuses": [dict(r) for r in db.execute("SELECT status,COUNT(*) count FROM boards WHERE run_id=? GROUP BY status", (run_id,))]}
        write_json(ROOT / "data" / "progress.json", value)
        print(f"{completed:,}/{len(registry):,} boards | {live:,} listed jobs | {companies:,} company feeds | {errors:,} errors | {status}", flush=True)

    progress()
    iterator = iter(pending)
    workers = max(1, min(args.workers, 8))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {}

        def schedule():
            while not stop and len(futures) < workers:
                b = next(iterator, None)
                if b is None:
                    break
                futures[pool.submit(fetch_board, b)] = b

        schedule()
        last_progress = time.monotonic()
        while futures:
            finished, _ = wait(futures, timeout=1, return_when=FIRST_COMPLETED)
            for future in finished:
                b = futures.pop(future)
                result = future.result()
                persist_board(db, result, run_id, utcnow())
                db.commit()
                completed += 1
                counts[result["status"]] += 1
                if result["jobs"] and (completed <= 15 or len(result["jobs"]) > 2000):
                    print(f"  {b['platform']}/{b['board']}: {len(result['jobs']):,} jobs ({result['status']})", flush=True)
            if (finished and completed % 25 == 0) or time.monotonic() - last_progress > 15:
                progress()
                last_progress = time.monotonic()
            schedule()
    status = "interrupted" if stop else "completed"
    db.execute("UPDATE runs SET finished_at=? WHERE id=?", (utcnow(), run_id))
    progress(status)
    if not args.no_export:
        export_data(argparse.Namespace(output=str(OUTPUT), include_descriptions=False), db)


def safe_cell(value):
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def export_data(args, db=None):
    own_db = db is None
    db = db or connect(readonly=True)
    if own_db:
        db.execute("BEGIN")
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    fields = FIELDS if args.include_descriptions else [f for f in FIELDS if f != "description"]
    rows = db.execute("SELECT * FROM jobs WHERE active=1 ORDER BY company COLLATE NOCASE,company_key,title COLLATE NOCASE,key")
    companies, platform_counts, total = [], Counter(), 0
    current_key, current_rows = None, []
    all_path = out / "all_jobs.csv.tmp"
    company_json = out / "company_data"
    company_json.mkdir(exist_ok=True)
    csvzip = zipfile.ZipFile(out / "company_csvs.zip.tmp", "w", zipfile.ZIP_DEFLATED, compresslevel=6)

    def finish_company():
        if not current_rows:
            return
        first = current_rows[0]
        stem = re.sub(r"[^a-zA-Z0-9._-]+", "_", first["company_key"])[:150]
        buffer = io.StringIO(newline="")
        writer = csv.writer(buffer)
        writer.writerow(fields)
        writer.writerows([[safe_cell(r.get(f, "")) for f in fields] for r in current_rows])
        csvzip.writestr(stem + ".csv", "\ufeff" + buffer.getvalue())
        # Workbook builder consumes one company at a time, keeping memory bounded.
        data_path = company_json / f"{stem}.json"
        write_json(data_path, {"fields": fields, "company": first["company"], "company_key": first["company_key"], "rows": [{f: r.get(f) for f in fields} for r in current_rows]})
        companies.append({"company": first["company"], "company_key": first["company_key"], "platform": first["platform"], "jobs": len(current_rows), "data_file": f"{stem}.json", "csv_file": stem + ".csv", "data_sha256": hashlib.sha256(data_path.read_bytes()).hexdigest()})

    with all_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(fields)
        for row in rows:
            row = dict(row)
            if row["company_key"] != current_key:
                finish_company()
                current_key, current_rows = row["company_key"], []
            writer.writerow([safe_cell(row.get(f, "")) for f in fields])
            current_rows.append(row)
            platform_counts[row["platform"]] += 1
            total += 1
        finish_company()
    csvzip.close()
    all_path.replace(out / "all_jobs.csv")
    (out / "company_csvs.zip.tmp").replace(out / "company_csvs.zip")
    with (out / "companies.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["company", "company_key", "platform", "jobs", "csv_file"])
        writer.writeheader()
        writer.writerows([{k: safe_cell(c[k]) for k in writer.fieldnames} for c in companies])
    with (out / "collection_log.csv").open("w", encoding="utf-8-sig", newline="") as f:
        records = db.execute("SELECT * FROM boards ORDER BY platform,board")
        writer = csv.writer(f)
        writer.writerow([d[0] for d in records.description])
        writer.writerows([[safe_cell(v) for v in r] for r in records])
    snapshot = {"exported_at": utcnow(), "total_jobs": total, "total_companies": len(companies),
        "platforms": dict(platform_counts), "fields": fields, "companies": companies,
        "active_definition": "Present in an employer's public feed or sitemap at checked_at. Individual application endpoints are not all tested. Older posting dates can still be listed.",
        "company_identity": "Company keys are platform:tenant. Names from slugs are display labels; cross-platform companies are not guessed/merged.",
        "description_policy": "Full available descriptions remain in SQLite; pass --include-descriptions to add them to CSV exports.",
        "date_policy": "Missing dates are blank. Greenhouse updated_at is a modification date. Workday relative dates are retained verbatim in date_note.",
        "sources": ["https://github.com/strelov1/freehire", "https://github.com/Riley-Dorrington/job-board-aggregator", "https://github.com/mherzog4/job-boards"],
        "dataset_license": "Riley-Dorrington company lists: CC BY-NC 4.0. Derived registry/export for noncommercial use; original postings remain their owners' content."}
    write_json(out / "manifest.json", snapshot)
    print(f"Exported {total:,} jobs / {len(companies):,} company feeds to {out}", flush=True)
    if own_db:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Collect public employer job feeds and export local files.")
    sub = parser.add_subparsers(dest="command", required=True)
    scan = sub.add_parser("scrape")
    scan.add_argument("--platforms", default="")
    scan.add_argument("--board", default="")
    scan.add_argument("--limit", type=int)
    scan.add_argument("--workers", type=int, default=8)
    scan.add_argument("--resume", action="store_true")
    scan.add_argument("--no-export", action="store_true")
    exp = sub.add_parser("export")
    exp.add_argument("--output", default=str(OUTPUT))
    exp.add_argument("--include-descriptions", action="store_true")
    sub.add_parser("registry")
    args = parser.parse_args()
    if args.command == "scrape":
        scrape(args)
    elif args.command == "export":
        export_data(args)
    else:
        print(json.dumps(dict(Counter(b["platform"] for b in build_registry())), indent=2))


if __name__ == "__main__":
    main()
