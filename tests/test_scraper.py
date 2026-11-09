import argparse
import csv
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from scraper.adapters import canonical_url, date_value, fetch_board, normalize, workplace, FetchError
from scraper.cli import export_data
from scraper.store import connect, persist_board


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = connect(Path(self.temp.name) / "test.sqlite")
        self.board = {"platform": "greenhouse", "board": "sample", "company": "Sample"}
        self.now = "2026-10-30T04:00:00Z"

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def job(self, job_id="42", **kw):
        return normalize(self.board, "https://boards-api.greenhouse.io/v1/boards/sample/jobs", job_id=job_id, title="Engineer", url=f"https://jobs.example.com/{job_id}", **kw)

    def persist(self, jobs, status="ok", run="run1", board=None):
        persist_board(self.db, {"board": board or self.board, "jobs": jobs, "status": status, "http_status": 200}, run, self.now)
        self.db.commit()

    def test_partial_and_failed_boards_do_not_retire_jobs(self):
        self.persist([self.job("1"), self.job("2")])
        self.persist([self.job("1")], "partial", "run2")
        self.persist([], "error", "run3")
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM jobs WHERE active=1").fetchone()[0], 2)
        self.persist([self.job("1")], "ok", "run4")
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM jobs WHERE active=1").fetchone()[0], 1)

    def test_empty_success_retires_and_later_reappearance_preserves_first_seen(self):
        self.persist([self.job()])
        self.persist([], run="run2")
        self.assertEqual(self.db.execute("SELECT active FROM jobs").fetchone()[0], 0)
        self.persist([self.job()], run="run3")
        row = self.db.execute("SELECT active,first_seen,last_run FROM jobs").fetchone()
        self.assertEqual(tuple(row), (1, self.now, "run3"))

    def test_board_namespaces_and_full_text_index(self):
        self.persist([self.job()])
        other = dict(self.board, board="other", company="Other")
        other_job = normalize(other, "https://example.com", job_id="42", title="Designer", url="https://example.com/designer")
        self.persist([other_job], board=other)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0], 2)
        self.persist([], run="run2")
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM jobs WHERE active=1").fetchone()[0], 1)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM jobs_fts WHERE jobs_fts MATCH 'Designer'").fetchone()[0], 1)

    def test_workday_same_requisition_across_sites(self):
        first = {"platform": "workday", "board": "sample|wd1|external", "company": "Sample"}
        second = dict(first, board="sample|wd1|other")
        a = normalize(first, "https://example.com", job_id="REQ1", title="Engineer", url="https://example.com/role")
        b = normalize(second, "https://example.com", job_id="REQ1", title="Engineer", url="https://example.com/role")
        self.assertEqual(a["key"], b["key"])
        self.persist([a], board=first)
        self.persist([b], run="run2", board=second)
        self.persist([], run="run2", board=second)
        self.assertEqual(self.db.execute("SELECT active FROM jobs").fetchone()[0], 1)

    def test_missing_values_and_dates_are_not_fabricated(self):
        self.assertEqual(workplace(location="London"), "Not specified")
        self.assertEqual(workplace("Hybrid", "Remote, US", True), "Hybrid")
        self.assertEqual(workplace(location="Remote - India"), "Remote")
        self.assertEqual(date_value("Posted 30+ Days Ago"), "")
        self.assertEqual(date_value(1600000000000, True)[:10], "2020-09-13")
        self.assertEqual(canonical_url("https://jobs.example.com/x?gh_jid=1&utm_source=spam#apply"), "https://jobs.example.com/x?gh_jid=1")
        self.assertEqual(canonical_url("javascript:alert(1)"), "")

    def test_ashby_unlisted_postings_are_excluded(self):
        class Response:
            def json(self):
                return {"jobs": [{"id":"a","title":"Live","jobUrl":"https://example.com/a","isListed":True},{"id":"b","title":"Draft","jobUrl":"https://example.com/b","isListed":False}]}
        with patch("scraper.adapters.request", return_value=Response()):
            result = fetch_board({"platform":"ashby","board":"sample","company":"Sample"})
        self.assertEqual([j["title"] for j in result["jobs"]], ["Live"])

    def test_workday_truncation_is_partial(self):
        class Response:
            def __init__(self, data): self.data = data
            def json(self): return self.data
        page = Response({"total":2,"jobPostings":[{"title":"Engineer","externalPath":"/job/role_REQ1","bulletFields":["REQ1"]}]})
        empty = Response({"total":2,"jobPostings":[]})
        with patch("scraper.adapters.request", side_effect=[page, empty]), patch("scraper.adapters.time.sleep"):
            result = fetch_board({"platform":"workday","board":"sample|wd1|external","company":"Sample"})
        self.assertEqual(result["status"], "partial")
        self.assertEqual(len(result["jobs"]), 1)

    def test_export_reconciles_company_files_and_neutralizes_formulas(self):
        j = self.job()
        j["title"] = "=HYPERLINK(\"https://example.com\")"
        self.persist([j, self.job("43")])
        out = Path(self.temp.name) / "exports"
        export_data(argparse.Namespace(output=str(out), include_descriptions=False), self.db)
        with (out / "all_jobs.csv").open(encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 2)
        self.assertTrue(any(r["title"].startswith("'=") for r in rows))
        manifest = json.loads((out / "manifest.json").read_text())
        self.assertEqual(manifest["total_jobs"], sum(c["jobs"] for c in manifest["companies"]))
        with zipfile.ZipFile(out / "company_csvs.zip") as archive:
            self.assertEqual(len(archive.namelist()), 1)
            content = archive.read(archive.namelist()[0]).decode("utf-8-sig")
            self.assertEqual(len(list(csv.DictReader(content.splitlines()))), 2)


if __name__ == "__main__":
    unittest.main()
