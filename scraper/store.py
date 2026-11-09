from __future__ import annotations

import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "jobs.sqlite"
FIELDS = [
    "key", "company", "company_key", "platform", "board", "job_id", "title",
    "location", "workplace", "department", "employment_type", "published_at",
    "updated_at", "salary_min", "salary_max", "salary_currency", "salary_interval",
    "url", "apply_url", "source_url", "description", "checked_at", "date_note", "salary_text",
]


def connect(path=DB_PATH, readonly=False):
    path = Path(path)
    if readonly:
        db = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=30000")
        return db
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=30000")
    cols = ",".join(f'"{c}" {"REAL" if c in ("salary_min", "salary_max") else "TEXT"}' for c in FIELDS)
    db.executescript(f"""
    CREATE TABLE IF NOT EXISTS jobs ({cols}, active INTEGER NOT NULL DEFAULT 1,
       first_seen TEXT NOT NULL, last_run TEXT NOT NULL, PRIMARY KEY(key));
    CREATE INDEX IF NOT EXISTS jobs_company ON jobs(company_key, active);
    CREATE INDEX IF NOT EXISTS jobs_platform ON jobs(platform, active);
    CREATE INDEX IF NOT EXISTS jobs_date ON jobs(updated_at DESC);
    CREATE INDEX IF NOT EXISTS jobs_workplace ON jobs(workplace, active);
    CREATE INDEX IF NOT EXISTS jobs_board ON jobs(platform, board);
    CREATE INDEX IF NOT EXISTS jobs_summary ON jobs(active,platform,company_key,workplace,checked_at,company);
    CREATE INDEX IF NOT EXISTS jobs_source_date ON jobs(COALESCE(NULLIF(published_at,''),NULLIF(updated_at,''),'') DESC,key) WHERE active=1;
    CREATE INDEX IF NOT EXISTS jobs_company_title ON jobs(company COLLATE NOCASE,title COLLATE NOCASE,key) WHERE active=1;
    CREATE INDEX IF NOT EXISTS jobs_title ON jobs(title COLLATE NOCASE,key) WHERE active=1;
    CREATE VIRTUAL TABLE IF NOT EXISTS jobs_fts USING fts5(title,company,location,department,content='jobs',content_rowid='rowid',tokenize='unicode61');
    CREATE TRIGGER IF NOT EXISTS jobs_ai AFTER INSERT ON jobs BEGIN
      INSERT INTO jobs_fts(rowid,title,company,location,department) VALUES(new.rowid,new.title,new.company,new.location,new.department);
    END;
    CREATE TRIGGER IF NOT EXISTS jobs_ad AFTER DELETE ON jobs BEGIN
      INSERT INTO jobs_fts(jobs_fts,rowid,title,company,location,department) VALUES('delete',old.rowid,old.title,old.company,old.location,old.department);
    END;
    CREATE TRIGGER IF NOT EXISTS jobs_au AFTER UPDATE ON jobs BEGIN
      INSERT INTO jobs_fts(jobs_fts,rowid,title,company,location,department) VALUES('delete',old.rowid,old.title,old.company,old.location,old.department);
      INSERT INTO jobs_fts(rowid,title,company,location,department) VALUES(new.rowid,new.title,new.company,new.location,new.department);
    END;
    CREATE TABLE IF NOT EXISTS boards (
      platform TEXT, board TEXT, company TEXT, status TEXT, http_status INTEGER,
      jobs INTEGER, checked_at TEXT, run_id TEXT, error TEXT,
      PRIMARY KEY(platform,board));
    CREATE TABLE IF NOT EXISTS runs (
      id TEXT PRIMARY KEY, started_at TEXT, finished_at TEXT, status TEXT,
      total_boards INTEGER, completed_boards INTEGER DEFAULT 0, jobs INTEGER DEFAULT 0,
      platforms TEXT, errors INTEGER DEFAULT 0);
    """)
    if "salary_text" not in {r[1] for r in db.execute("PRAGMA table_info(jobs)")}:
        db.execute("ALTER TABLE jobs ADD COLUMN salary_text TEXT DEFAULT ''")
    db.execute("UPDATE jobs SET salary_text=date_note,date_note='' WHERE platform='ashby' AND date_note!='' AND COALESCE(salary_text,'')=''")
    db.commit()
    return db


def persist_board(db, result, run_id, now):
    board = result["board"]
    platform = board["platform"]
    slug = board["board"]
    jobs = result["jobs"]
    # Only a completely successful board fetch may retire missing postings.
    # Failed/partial boards retain old observations with their original checked_at.
    if result["status"] == "ok":
        db.execute("UPDATE jobs SET active=0 WHERE platform=? AND board=? AND last_run!=?", (platform, slug, run_id))
    columns = FIELDS + ["active", "first_seen", "last_run"]
    updates = ",".join(f'"{f}"=excluded."{f}"' for f in FIELDS if f != "key")
    query = f'INSERT INTO jobs ({",".join(columns)}) VALUES ({",".join("?" for _ in columns)}) ON CONFLICT(key) DO UPDATE SET {updates},active=1,last_run=excluded.last_run'
    db.executemany(query, [[j.get(c, "") for c in FIELDS] + [1, now, run_id] for j in jobs])
    db.execute("""INSERT INTO boards VALUES (?,?,?,?,?,?,?,?,?)
      ON CONFLICT(platform,board) DO UPDATE SET company=excluded.company,status=excluded.status,
      http_status=excluded.http_status,jobs=excluded.jobs,checked_at=excluded.checked_at,
      run_id=excluded.run_id,error=excluded.error""",
      (platform, slug, board.get("company", slug), result["status"], result.get("http_status"),
       len(jobs), now, run_id, result.get("error", "")))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)
