"""Inspect a few public job-detail responses before building strict checks."""
import csv
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/active_validation/probes"
OUT.mkdir(parents=True, exist_ok=True)
samples = {}
with (ROOT / "outputs/united_states/us_jobs.csv").open(encoding="utf-8-sig", newline="") as f:
    for row in csv.DictReader(f):
        if row["platform"] not in samples:
            samples[row["platform"]] = row


def probe(pair):
    platform, row = pair
    targets = [("page", row["apply_url"])]
    if platform == "greenhouse":
        targets += [("api", f"https://boards-api.greenhouse.io/v1/boards/{row['board']}/jobs/{row['job_id']}?questions=true")]
    if platform == "workday":
        tenant, wd, site = row["board"].split("|")
        relative = row["url"].split("/job/", 1)[1]
        targets += [("api", f"https://{tenant}.{wd}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/job/{relative}")]
    results = []
    for kind, url in targets:
        try:
            response = requests.get(url, timeout=(5, 20), headers={"User-Agent": "JobAtlasLocal/1.0 (job availability checks; contact: s.b.m.rafi03@gmail.com)"})
            path = OUT / f"{platform}-{kind}.txt"
            path.write_text(response.text)
            results.append({"platform": platform, "kind": kind, "status": response.status_code,
                            "url": response.url, "bytes": len(response.content), "saved": str(path)})
        except Exception as exc:
            results.append({"platform": platform, "kind": kind, "error": str(exc)[:200]})
    return results


with ThreadPoolExecutor(max_workers=8) as pool:
    for result in pool.map(probe, samples.items()):
        print(json.dumps(result), flush=True)
