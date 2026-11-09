"""Download the reference repositories without modifying existing checkouts."""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "freehire": "https://github.com/strelov1/freehire.git",
    "job-board-aggregator": "https://github.com/Riley-Dorrington/job-board-aggregator.git",
    "job-boards": "https://github.com/mherzog4/job-boards.git",
}
versions = []
for name, url in SOURCES.items():
    target = ROOT / "sources" / name
    if not target.exists():
        subprocess.run(["git", "clone", "--depth", "1", url, str(target)], check=True)
    commit = subprocess.check_output(["git", "-C", str(target), "rev-parse", "HEAD"], text=True).strip()
    versions.append({"name": name, "repository": url.removesuffix(".git"), "commit": commit})
(ROOT / "source_versions.json").write_text(json.dumps(versions, indent=2) + "\n")
print("Reference repositories ready.")
