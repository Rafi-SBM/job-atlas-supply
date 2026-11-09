"""Recheck every delivered US job and retain only positive application evidence."""
from __future__ import annotations
import argparse
import asyncio
import csv
import hashlib
import json
import signal
import sqlite3
import ssl
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlsplit
import aiohttp
import certifi

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scraper.availability import evidence, non_vacancy, target
from scraper.us_locations import USLocations
from scraper.store import write_json

SOURCE = ROOT / "outputs/united_states/us_jobs.csv"
FOLDER = ROOT / "data/active_validation"
OUTPUT = ROOT / "outputs/united_states/active_only"
EXTRA_FIELDS = ["active_status", "active_verified_at", "verification_method", "verification_url", "verification_evidence"]


def utcnow():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


class Validator:
    def __init__(self, rows, workers=200, resume=False, retry_unconfirmed=False):
        FOLDER.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(FOLDER / "results.sqlite")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("""CREATE TABLE IF NOT EXISTS checks (
            key TEXT PRIMARY KEY, platform TEXT, status TEXT, verified_at TEXT,
            reason TEXT, url TEXT, http_status INTEGER, updates TEXT)""")
        fingerprint = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
        fingerprint_file = FOLDER / "source_sha256.txt"
        previous = fingerprint_file.read_text().strip() if fingerprint_file.exists() else None
        if not resume or previous != fingerprint:
            self.db.execute("DELETE FROM checks")
        else:
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat(timespec="seconds").replace("+00:00", "Z")
            self.db.execute("DELETE FROM checks WHERE verified_at<?", (cutoff,))
        fingerprint_file.write_text(fingerprint + "\n")
        if retry_unconfirmed:
            self.db.execute("DELETE FROM checks WHERE status='unconfirmed'")
        self.db.commit()
        self.rows = rows
        self.us = USLocations({r["location"] for r in rows})
        self.global_limit = asyncio.Semaphore(workers)
        self.host_limits, self.host_locks = {}, {}
        self.next_start, self.holds = defaultdict(float), defaultdict(float)
        self.started = time.monotonic()
        self.started_at = utcnow()
        self.finished = False
        self.counts = Counter(r[0] for r in self.db.execute("SELECT status FROM checks"))
        self.platforms = Counter(r[0] for r in self.db.execute("SELECT platform FROM checks"))
        self.total = len(rows)
        self.since_commit = 0

    async def fetch(self, session, url):
        host = urlsplit(url).hostname
        common = host in {"boards-api.greenhouse.io", "jobs.lever.co", "jobs.eu.lever.co", "jobs.ashbyhq.com"}
        cap = 64 if host == "boards-api.greenhouse.io" else 32 if host in {"jobs.lever.co", "jobs.eu.lever.co"} else 24 if common else 3
        rate = 60 if host == "boards-api.greenhouse.io" else 28 if host in {"jobs.lever.co", "jobs.eu.lever.co"} else 24 if common else 5
        sem = self.host_limits.setdefault(host, asyncio.Semaphore(cap))
        lock = self.host_locks.setdefault(host, asyncio.Lock())
        async with self.global_limit, sem:
            for attempt in range(3):
                async with lock:
                    delay = max(self.next_start[host], self.holds[host]) - time.monotonic()
                    if delay > 0:
                        await asyncio.sleep(min(delay, 120))
                    self.next_start[host] = time.monotonic() + 1 / rate
                try:
                    async with session.get(url, allow_redirects=True) as response:
                        code, final = response.status, str(response.url)
                        if code in {429, 502, 503, 504} and attempt < 2:
                            retry = response.headers.get("Retry-After", "")
                            try:
                                seconds = float(retry)
                            except ValueError:
                                try:
                                    seconds = (parsedate_to_datetime(retry) - datetime.now(timezone.utc)).total_seconds()
                                except (TypeError, ValueError):
                                    seconds = 2 ** (attempt + 1)
                            if seconds > 120:
                                self.holds[host] = max(self.holds[host], time.monotonic() + seconds)
                                return code, final, ""
                            if code == 429:
                                self.holds[host] = max(self.holds[host], time.monotonic() + max(2, seconds))
                            await asyncio.sleep(max(1, seconds))
                            continue
                        if code != 200:
                            return code, final, ""
                        raw = await response.read()
                        if len(raw) > 5_000_000:
                            return 0, final, ""
                        return code, final, raw.decode(response.charset or "utf-8", errors="replace")
                except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                    if attempt == 2:
                        return 0, url, type(exc).__name__
                    await asyncio.sleep(2 ** attempt)
        return 0, url, "Retry budget exhausted"

    async def check(self, session, row):
        code, updates, url = None, {}, ""
        if non_vacancy(row["title"]):
            status, reason = "excluded_general", "Generic application, talent pool, future-interest or non-vacancy title"
        else:
            try:
                url = target(row)
                code, final, body = await self.fetch(session, url)
                url = final
                if code in {404, 410}:
                    status, reason = "closed", f"Job/application endpoint returned HTTP {code}"
                elif code != 200:
                    status, reason = "unconfirmed", f"Application check unavailable (HTTP {code or 'network failure'})"
                else:
                    status, reason, updates = evidence(row, body, final)
                    if status == "open":
                        match, why = self.us.match(updates["location"])
                        if not match:
                            status, reason = "out_of_scope", f"Current location not US-only: {why}"
                        else:
                            updates["us_location_evidence"] = why
            except Exception as exc:
                status, reason = "unconfirmed", f"Cannot positively verify: {type(exc).__name__}: {str(exc)[:100]}"
        self.db.execute("INSERT OR REPLACE INTO checks VALUES(?,?,?,?,?,?,?,?)", (
            row["key"], row["platform"], status, utcnow(), reason, url, code, json.dumps(updates)))
        self.counts[status] += 1
        self.platforms[row["platform"]] += 1
        self.since_commit += 1
        if self.since_commit >= 100:
            self.db.commit()
            self.since_commit = 0

    def progress(self, status="running"):
        self.db.commit()
        value = {"status": status, "started_at": self.started_at, "updated_at": utcnow(),
                 "candidates": self.total, "checked": sum(self.counts.values()),
                 "remaining": self.total - sum(self.counts.values()), "results": dict(self.counts),
                 "platforms_checked": dict(self.platforms), "elapsed_seconds": round(time.monotonic() - self.started)}
        write_json(FOLDER / "progress.json", value)
        print(json.dumps(value), flush=True)

    async def reporter(self):
        while not self.finished:
            self.progress()
            await asyncio.sleep(20)

    async def run(self, limit=None):
        done = {r[0] for r in self.db.execute("SELECT key FROM checks")}
        pending = [r for r in self.rows if r["key"] not in done]
        # Independent source queues prevent a slower host from occupying all
        # workers while other employers are ready to answer.
        buckets = defaultdict(list)
        for row in pending:
            buckets[row["platform"]].append(row)
        if limit:
            sample = []
            while any(buckets.values()) and len(sample) < limit:
                for p in sorted(buckets):
                    n = min(20, limit - len(sample))
                    if n:
                        sample.extend(buckets[p][-n:])
                        del buckets[p][-n:]
            buckets = defaultdict(list)
            for row in sample:
                buckets[row["platform"]].append(row)
        queues = {}
        for platform, values in buckets.items():
            queue = asyncio.Queue()
            for row in values:
                queue.put_nowait(row)
            queues[platform] = queue
        headers = {"User-Agent": "JobAtlasLocal/1.0 (application availability checks; contact: s.b.m.rafi03@gmail.com)",
                   "Accept": "application/json,text/html;q=0.9,*/*;q=0.8"}
        connector = aiohttp.TCPConnector(limit=220, ssl=ssl.create_default_context(cafile=certifi.where()), ttl_dns_cache=600)
        timeout = aiohttp.ClientTimeout(total=28, connect=7, sock_read=20)
        async with aiohttp.ClientSession(connector=connector, timeout=timeout, headers=headers, trust_env=True) as session:
            async def worker(queue):
                while not queue.empty():
                    try:
                        row = queue.get_nowait()
                    except asyncio.QueueEmpty:
                        return
                    await self.check(session, row)
                    queue.task_done()
            reporter = asyncio.create_task(self.reporter())
            completed = False
            try:
                allocation = {"greenhouse": 72, "lever": 36, "ashby": 26, "bamboohr": 72, "workday": 6}
                await asyncio.gather(*(worker(queue) for platform, queue in queues.items()
                                       for _ in range(allocation.get(platform, 4))))
                completed = True
            finally:
                self.finished = True
                reporter.cancel()
                self.progress(("sample_complete" if limit else "completed") if completed else "interrupted")
        if not limit:
            self.export()

    def export(self):
        OUTPUT.mkdir(parents=True, exist_ok=True)
        results = {r[0]: r[1:] for r in self.db.execute("SELECT key,status,verified_at,reason,url,http_status,updates FROM checks")}
        assert len(results) == len(self.rows), "All candidates must be checked before final export"
        fields = list(self.rows[0]) + EXTRA_FIELDS
        count = 0
        destination = OUTPUT / "active_us_jobs.csv"
        temp = destination.with_suffix(".csv.tmp")
        with temp.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for original in self.rows:
                state, when, reason, url, code, updates = results[original["key"]]
                if state != "open":
                    continue
                row = dict(original)
                row.update(json.loads(updates))
                row.update(active_status="Open for applications when checked", active_verified_at=when,
                           verification_method="Job-specific application availability check",
                           verification_url=url, verification_evidence=reason)
                for k, v in row.items():
                    if isinstance(v, str) and re_formula(v):
                        row[k] = "'" + v
                writer.writerow(row)
                count += 1
        temp.replace(destination)
        summary = {"exported_at": utcnow(), "source": str(SOURCE),
                   "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                   "candidates": len(self.rows), "active_jobs": count, "results": dict(self.counts),
                   "policy": "Only positive, job-specific application-page or application-schema evidence. Closed, generic, expired, non-US and unconfirmed results excluded. No applications submitted.",
                   "csv": str(destination), "excluded_jobs": len(self.rows) - count,
                   "verification_started_at": self.db.execute("SELECT MIN(verified_at) FROM checks").fetchone()[0],
                   "verification_finished_at": self.db.execute("SELECT MAX(verified_at) FROM checks").fetchone()[0],
                   "csv_sha256": hashlib.sha256(destination.read_bytes()).hexdigest()}
        write_json(OUTPUT / "summary.json", summary)
        print(json.dumps(summary, indent=2), flush=True)


def re_formula(value):
    return bool(value and value.lstrip().startswith(("=", "+", "-", "@")))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int)
    parser.add_argument("--resume", action="store_true", help="Resume checks against the same snapshot; results older than six hours are rechecked")
    parser.add_argument("--retry-unconfirmed", action="store_true", help="Retry inconclusive checks while resuming")
    args = parser.parse_args()
    with SOURCE.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len({r["key"] for r in rows}) == len(rows)
    assert all(r["country"] == "United States" for r in rows)
    asyncio.run(Validator(rows, resume=args.resume, retry_unconfirmed=args.retry_unconfirmed).run(args.limit))


if __name__ == "__main__":
    main()
