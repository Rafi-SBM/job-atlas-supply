from __future__ import annotations

import json
import re
from pathlib import Path
from .store import ROOT, write_json

PLATFORMS = ("greenhouse", "ashby", "lever", "bamboohr", "workday", "paylocity", "icims",
             "workable", "recruitee", "smartrecruiters", "personio", "breezy")

DISPLAY_NAMES = {
    "openai": "OpenAI", "anthropic": "Anthropic", "stripe": "Stripe", "airbnb": "Airbnb",
    "figma": "Figma", "databricks": "Databricks", "notion": "Notion", "vercel": "Vercel",
    "gitlab": "GitLab", "1password": "1Password", "posthog": "PostHog", "supabase": "Supabase",
    "netflix": "Netflix", "spotify": "Spotify", "cursor": "Cursor", "replit": "Replit",
}


def company_name(slug):
    return DISPLAY_NAMES.get(slug.lower(), re.sub(r"[-_]+", " ", slug).strip().title())


def build_registry():
    entries = {}

    def add(platform, board, company=None, source=""):
        board = str(board).strip()
        if not board or len(board) > 200 or platform not in PLATFORMS:
            return
        if platform != "workday" and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_. -]*", board):
            return
        key = (platform, board.lower())
        label = company or company_name(board.split("|")[0])
        if key not in entries:
            entries[key] = {"platform": platform, "board": board, "company": label, "registries": [source]}
        elif source not in entries[key]["registries"]:
            entries[key]["registries"].append(source)

    folder = ROOT / "sources" / "job-board-aggregator" / "data"
    for platform in PLATFORMS:
        path = folder / ("paylocity_companies_clean.json" if platform == "paylocity" else f"{platform}_companies.json")
        if path.exists():
            for row in json.loads(path.read_text()):
                add(platform, row.get("guid"), row.get("name"), "Riley-Dorrington/job-board-aggregator") if isinstance(row, dict) else add(platform, row, source="Riley-Dorrington/job-board-aggregator")
    path = ROOT / "sources" / "job-boards" / "boards.seed.json"
    if path.exists():
        for platform, slugs in json.loads(path.read_text()).items():
            for slug in slugs:
                add(platform, slug, source="mherzog4/job-boards")

    # Freehire's board database is not distributed. Harvest only public board
    # addresses mentioned in its adapter examples/tests, then validate live.
    patterns = {
        "greenhouse": r"(?:boards|job-boards)(?:\.eu)?\.greenhouse\.io/([A-Za-z0-9_-]+)",
        "ashby": r"jobs\.ashbyhq\.com/([A-Za-z0-9_.-]+)",
        "lever": r"jobs\.(?:eu\.)?lever\.co/([A-Za-z0-9_.-]+)",
        "workable": r"apply\.workable\.com/([A-Za-z0-9_-]+)",
        "recruitee": r"([A-Za-z0-9_-]+)\.recruitee\.com",
        "smartrecruiters": r"(?:jobs\.smartrecruiters\.com/|api\.smartrecruiters\.com/v1/companies/)([A-Za-z0-9_-]+)",
        "personio": r"([A-Za-z0-9_-]+)\.jobs\.personio\.(?:com|de)",
        "breezy": r"([A-Za-z0-9_-]+)\.breezy\.hr",
    }
    block = {"example", "acme", "test", "foo", "company", "embed", "api", "www", "v1", "x", "demo", "fake", "testco"}
    for path in (ROOT / "sources" / "freehire" / "internal" / "ingest" / "sources").glob("*.go"):
        text = path.read_text()
        for platform, pattern in patterns.items():
            for slug in re.findall(pattern, text):
                if len(slug) >= 3 and slug.lower() not in block:
                    add(platform, slug, source="strelov1/freehire")
    # Prioritize known active seed employers, then distribute platforms evenly.
    seed_order = ["openai", "anthropic", "stripe", "figma", "vercel", "cursor", "airbnb", "netflix", "spotify"]
    rows = sorted(entries.values(), key=lambda x: (seed_order.index(x["board"].lower()) if x["board"].lower() in seed_order else 999, x["board"].lower(), x["platform"]))
    if not rows:
        raise RuntimeError("No company lists. Clone the source repositories as described in README.md.")
    write_json(ROOT / "data" / "registry.json", rows)
    return rows
