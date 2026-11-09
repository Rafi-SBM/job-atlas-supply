import "server-only";
import fs from "node:fs";
import path from "node:path";
import { DatabaseSync } from "node:sqlite";

export type Job = {
  key: string; company: string; company_key: string; platform: string; board: string;
  job_id: string; title: string; location: string; workplace: string; department: string;
  employment_type: string; published_at: string; updated_at: string; checked_at: string;
  salary_min: number | null; salary_max: number | null; salary_currency: string;
  salary_interval: string; url: string; apply_url: string; source_url: string;
  description?: string; date_note: string; salary_text: string;
  role_group?: string; us_state?: string; us_city?: string; is_us?: number;
  active_status?: string; verification_evidence?: string; verified_at?: string;
};

export type Filters = {
  q?: string;
  title?: string;
  location?: string;
  platform?: string;
  company?: string;
  workplace?: string;
  sort?: string;
  page?: string | number;
  saved?: string;
  role_group?: string;
  state?: string;
  us_state?: string;
  city?: string;
  us_city?: string;
  remote?: string | boolean;
  us_only?: string | boolean;
  active_only?: string | boolean;
  since?: string;
  limit?: string | number;
  exclude_keys?: string;
  exclude_companies?: string;
  distinct_company?: string | boolean;
};

export type Company = { company: string; company_key: string; platform: string; jobs: number };

export type Stats = {
  total: number;
  companies: number;
  remote: number;
  us_jobs: number;
  us_remote: number;
  platforms: { platform: string; jobs: number; companies: number }[];
  checked_at: string;
  progress: { status: string; completed_boards: number; total_boards: number; errors: number; updated_at: string } | null;
};

export type Metadata = {
  role_groups: { name: string; jobs: number }[];
  states: { state: string; jobs: number }[];
  platforms: { platform: string; jobs: number; companies: number }[];
  total_jobs: number;
  total_us_jobs: number;
  total_us_remote: number;
  checked_at: string;
};

export type Results = { jobs: Job[]; total: number; page: number; pages: number; limit: number };

const DB_PATH = path.join(process.cwd(), "data", "jobs.sqlite");
let database: DatabaseSync | undefined;

export function db(): DatabaseSync | null {
  if (!fs.existsSync(DB_PATH)) return null;
  if (!database) {
    database = new DatabaseSync(DB_PATH, { readOnly: true });
    database.exec("PRAGMA busy_timeout=10000");
  }
  return database;
}

const columns = "j.key,j.company,j.company_key,j.platform,j.board,j.job_id,j.title,j.location,j.workplace,j.department,j.employment_type,j.published_at,j.updated_at,j.checked_at,j.salary_min,j.salary_max,j.salary_currency,j.salary_interval,j.url,j.apply_url,j.source_url,j.date_note,j.salary_text,j.role_group,j.us_state,j.us_city,j.is_us,j.active_status,j.verification_evidence,j.verified_at";

export function where(filters: Filters) {
  const clauses = ["j.active=1"];
  const values: (string | number)[] = [];
  const search = filters.q?.trim().slice(0, 200);

  if (search) {
    const tokens = search.match(/[\p{L}\p{N}]+/gu) || [];
    if (tokens.length) {
      clauses.push("j.rowid IN (SELECT rowid FROM jobs_fts WHERE jobs_fts MATCH ?)");
      values.push(tokens.map(t => `"${t}"*`).join(" AND "));
    } else {
      clauses.push("0=1");
    }
  }

  if (filters.title) {
    clauses.push("j.title LIKE ? ESCAPE '\\'");
    values.push(`%${filters.title.slice(0, 150).replace(/[\\%_]/g, "\\$&")}%`);
  }

  for (const field of ["platform", "company", "workplace"] as const) {
    if (filters[field]) {
      clauses.push(`j.${field === "company" ? "company_key" : field}=?`);
      values.push(filters[field]!.slice(0, 250));
    }
  }

  if (filters.location) {
    clauses.push("j.location LIKE ? ESCAPE '\\'");
    values.push(`%${filters.location.slice(0, 150).replace(/[\\%_]/g, "\\$&")}%`);
  }

  const role = filters.role_group?.trim();
  if (role) {
    clauses.push("j.role_group=?");
    values.push(role);
  }

  const stateCode = (filters.state || filters.us_state)?.trim().toUpperCase();
  if (stateCode) {
    clauses.push("j.us_state=?");
    values.push(stateCode);
  }

  const city = (filters.city || filters.us_city)?.trim();
  if (city) {
    clauses.push("j.us_city LIKE ? ESCAPE '\\'");
    values.push(`%${city.slice(0, 100).replace(/[\\%_]/g, "\\$&")}%`);
  }

  if (filters.us_only === "1" || filters.us_only === true || filters.us_only === "true") {
    clauses.push("j.is_us=1");
  }

  if (filters.remote === "1" || filters.remote === true || filters.remote === "true") {
    clauses.push("j.workplace='Remote'");
  }

  if (filters.active_only === "1" || filters.active_only === true || filters.active_only === "true") {
    clauses.push("j.active_status='open'");
  }

  if (filters.since) {
    clauses.push("(j.published_at >= ? OR j.checked_at >= ?)");
    values.push(filters.since, filters.since);
  }

  if (filters.exclude_keys) {
    const excluded = filters.exclude_keys.split(",").map(k => k.trim()).filter(Boolean).slice(0, 500);
    if (excluded.length) {
      clauses.push(`j.key NOT IN (${excluded.map(() => "?").join(",")})`);
      values.push(...excluded);
    }
  }

  if (filters.exclude_companies) {
    const excludedComps = filters.exclude_companies.split(",").map(c => c.trim().toLowerCase()).filter(Boolean).slice(0, 500);
    if (excludedComps.length) {
      clauses.push(`LOWER(j.company) NOT IN (${excludedComps.map(() => "?").join(",")})`);
      values.push(...excludedComps);
    }
  }

  if (filters.saved !== undefined) {
    let keys: string[] = [];
    try {
      const v = JSON.parse(filters.saved);
      if (Array.isArray(v)) keys = v.filter(x => typeof x === "string").slice(0, 500);
    } catch {}
    if (!keys.length) clauses.push("0=1");
    else {
      clauses.push(`j.key IN (${keys.map(() => "?").join(",")})`);
      values.push(...keys);
    }
  }

  return { sql: clauses.join(" AND "), values };
}

export function getJobs(filters: Filters = {}): Results {
  const database = db();
  const limitVal = Math.min(200, Math.max(1, Number(filters.limit || 25)));
  if (!database) return { jobs: [], total: 0, page: 1, pages: 1, limit: limitVal };

  const { sql, values } = where(filters);
  const isDistinctCompany = filters.distinct_company === "1" || filters.distinct_company === true || filters.distinct_company === "true";
  const countTarget = isDistinctCompany ? "COUNT(DISTINCT j.company_key)" : "COUNT(*)";
  const groupBy = isDistinctCompany ? "GROUP BY j.company_key" : "";

  const total = Number(database.prepare(`SELECT ${countTarget} total FROM jobs j WHERE ${sql}`).get(...values)?.total || 0);
  const pages = Math.max(1, Math.ceil(total / limitVal));
  const requested = Number(filters.page || 1);
  const page = Math.min(pages, Math.max(1, Number.isFinite(requested) ? Math.floor(requested) : 1));

  const sort = filters.sort === "company"
    ? "j.company COLLATE NOCASE,j.title COLLATE NOCASE"
    : filters.sort === "title"
    ? "j.title COLLATE NOCASE"
    : "COALESCE(NULLIF(j.published_at,''),NULLIF(j.updated_at,''),'') DESC";

  const orderedIndex = filters.sort === "company" ? "jobs_company_title" : filters.sort === "title" ? "jobs_title" : "jobs_source_date";
  const hint = sql === "j.active=1" && !isDistinctCompany ? `INDEXED BY ${orderedIndex}` : "";

  const jobs = database.prepare(
    `SELECT ${columns} FROM jobs j WHERE j.rowid IN (SELECT j.rowid FROM jobs j ${hint} WHERE ${sql} ${groupBy} ORDER BY ${sort},j.key LIMIT ? OFFSET ?) ORDER BY ${sort},j.key`
  ).all(...values, limitVal, (page - 1) * limitVal).map(row => ({...row})) as unknown as Job[];

  return { jobs, total, page, pages, limit: limitVal };
}

let cachedMetadata: { at: number; value: Metadata } | undefined;
export function getMetadata(): Metadata {
  if (cachedMetadata && Date.now() - cachedMetadata.at < 60000) return cachedMetadata.value;
  const metaPath = path.join(process.cwd(), "data", "metadata.json");
  if (fs.existsSync(metaPath)) {
    try {
      const data = JSON.parse(fs.readFileSync(metaPath, "utf8")) as Metadata;
      cachedMetadata = { at: Date.now(), value: data };
      return data;
    } catch {}
  }

  const database = db();
  if (!database) {
    return { role_groups: [], states: [], platforms: [], total_jobs: 0, total_us_jobs: 0, total_us_remote: 0, checked_at: "" };
  }

  const roleRows = database.prepare(
    "SELECT role_group as name, COUNT(*) as jobs FROM jobs WHERE active=1 AND role_group != '' GROUP BY role_group ORDER BY jobs DESC"
  ).all().map(r => ({...r})) as { name: string; jobs: number }[];

  const stateRows = database.prepare(
    "SELECT us_state as state, COUNT(*) as jobs FROM jobs WHERE active=1 AND is_us=1 AND us_state != '' GROUP BY us_state ORDER BY jobs DESC"
  ).all().map(r => ({...r})) as { state: string; jobs: number }[];

  const platformRows = database.prepare(
    "SELECT platform, COUNT(*) as jobs, COUNT(DISTINCT company_key) as companies FROM jobs WHERE active=1 GROUP BY platform ORDER BY jobs DESC"
  ).all().map(r => ({...r})) as { platform: string; jobs: number; companies: number }[];

  const counts = database.prepare(
    "SELECT COUNT(*) as total, SUM(is_us=1) as us_total, SUM(is_us=1 AND workplace='Remote') as us_remote, MAX(checked_at) as checked_at FROM jobs WHERE active=1"
  ).get() as { total?: number; us_total?: number; us_remote?: number; checked_at?: string } | undefined;

  const value: Metadata = {
    role_groups: roleRows,
    states: stateRows,
    platforms: platformRows,
    total_jobs: Number(counts?.total || 0),
    total_us_jobs: Number(counts?.us_total || 0),
    total_us_remote: Number(counts?.us_remote || 0),
    checked_at: String(counts?.checked_at || "")
  };

  cachedMetadata = { at: Date.now(), value };
  return value;
}

let cachedStats: { at: number; value: Stats } | undefined;
export function getStats(): Stats {
  if (cachedStats && Date.now() - cachedStats.at < 15000) return cachedStats.value;
  const meta = getMetadata();
  let progress = null;
  try { progress = JSON.parse(fs.readFileSync(path.join(process.cwd(), "data", "progress.json"), "utf8")); } catch {}

  const value: Stats = {
    total: meta.total_jobs,
    companies: meta.platforms.reduce((acc, p) => acc + (p.companies || 0), 0),
    remote: meta.total_us_remote,
    us_jobs: meta.total_us_jobs,
    us_remote: meta.total_us_remote,
    checked_at: meta.checked_at,
    platforms: meta.platforms,
    progress
  };

  cachedStats = { at: Date.now(), value };
  return value;
}

export function getJobsBatch(keys: string[]): Job[] {
  const database = db();
  if (!database || !keys.length) return [];
  const safeKeys = keys.slice(0, 500);
  const placeholders = safeKeys.map(() => "?").join(",");
  return database.prepare(
    `SELECT ${columns} FROM jobs j WHERE j.key IN (${placeholders}) AND j.active=1`
  ).all(...safeKeys).map(row => ({...row})) as unknown as Job[];
}

export function getCompanies(q = "", limit = 100): Company[] {
  const database = db();
  if (!database) return [];
  return database.prepare("SELECT company,company_key,platform,COUNT(*) jobs FROM jobs WHERE active=1 AND company LIKE ? ESCAPE '\\' GROUP BY company_key ORDER BY jobs DESC,company LIMIT ?").all(`%${q.slice(0, 100).replace(/[\\%_]/g, "\\$&")}%`, limit).map(row => ({...row})) as Company[];
}

export function getJob(key: string): Job | null {
  return db()?.prepare("SELECT * FROM jobs WHERE key=? AND active=1").get(key) as Job | undefined || null;
}

export function exportRows(filters: Filters) {
  const query = where(filters);
  const hint = query.sql === "j.active=1" ? "INDEXED BY jobs_company_title" : "";
  return db()?.prepare(`SELECT ${columns} FROM jobs j ${hint} WHERE ${query.sql} ORDER BY j.company COLLATE NOCASE,j.title COLLATE NOCASE,j.key`).iterate(...query.values);
}

export function getDownloads() {
  const root = path.join(process.cwd(), "outputs", "job-atlas");
  return { csv: fs.existsSync(path.join(root, "all_jobs.csv")), company_csvs: fs.existsSync(path.join(root, "company_csvs.zip")), xlsx: fs.existsSync(path.join(root, "jobs_by_company.xlsx")), workbooks: fs.existsSync(path.join(root, "company_workbooks.zip")) };
}
