"""Finish the currently running full collection and produce verified exports."""
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NODE = Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"


def status(phase, **values):
    data = {"phase": phase, "updated_at": datetime.now(timezone.utc).isoformat(), **values}
    target = ROOT / "data/background_pipeline.json"
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2))
    temporary.replace(target)


def run(args, env=None):
    print("Running:", " ".join(str(a) for a in args), flush=True)
    subprocess.run([str(a) for a in args], cwd=ROOT, env=env, check=True)


def main():
    status("collecting")
    lock = ROOT / "data/scrape.lock"
    while lock.exists():
        try:
            os.kill(int(lock.read_text()), 0)
        except FileNotFoundError:
            break
        except (ProcessLookupError, ValueError):
            # A crash must not strand a stale lock and stop the requested background run.
            run([sys.executable, "-u", "-m", "scraper.cli", "scrape", "--resume", "--no-export"])
            break
        time.sleep(3)
    progress = json.loads((ROOT / "data/progress.json").read_text())
    if progress["status"] != "completed":
        status("stopped", reason="Collection interrupted; resume manually to continue.")
        raise SystemExit("The collection was interrupted. Resume it before producing final exports.")
    # Refresh the first provider collected before structured salary support was added.
    status("refreshing_compensation")
    run([sys.executable, "-u", "-m", "scraper.cli", "scrape", "--platforms", "ashby", "--no-export"])
    # Keep the delivered CSV and Excel archive consistent until the next complete
    # snapshot has passed verification. Work on a separate output directory.
    stage = ROOT / "outputs" / ".job-atlas-next"
    stage.mkdir(parents=True, exist_ok=True)
    current = ROOT / "outputs" / "job-atlas"
    status("exporting")
    run([sys.executable, "-u", "-m", "scraper.cli", "export", "--output", stage])
    if (current / "workbooks").exists():
        shutil.copytree(current / "workbooks", stage / "workbooks", dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("*.png", "*.inspect.ndjson"))
    env = dict(os.environ, JOB_ATLAS_EXPORT_DIR=str(stage))
    status("building_workbooks")
    run([NODE, "workbook/build.mjs", "--resume"], env=env)
    status("verifying")
    run([sys.executable, "-u", "scripts/package_workbooks.py"], env=env)
    previous = ROOT / "outputs" / ("job-atlas-previous-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    current.rename(previous)
    try:
        stage.rename(current)
    except BaseException:
        previous.rename(current)
        raise
    summary = json.loads((current / "verification.json").read_text())
    status("completed", **summary)
    print("All CSV and Excel exports are complete and reconciled.", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        status("failed", error=str(error))
        raise
