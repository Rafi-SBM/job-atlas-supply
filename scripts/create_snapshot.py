"""Export a consistent snapshot while live collection continues."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NODE = Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"
commands = [
    [sys.executable, "-u", "-m", "scraper.cli", "export"],
    [str(NODE), "workbook/build.mjs", "--resume"],
    [sys.executable, "-u", "scripts/package_workbooks.py"],
]
for command in commands:
    print("Running:", " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)
print("Snapshot CSV and all company worksheets are ready.", flush=True)
