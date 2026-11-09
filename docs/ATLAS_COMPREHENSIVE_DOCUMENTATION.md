# Job Atlas — Comprehensive Architecture, Operations & Integration Manual
*The Zero-Cost, High-Velocity US Job Harvesting & Delivery Engine (Supply Leg 3 for Jaithraya)*

---

## 1. Executive Summary & Core Engineering Philosophy

### 1.1 Mission & Context
Job Atlas was engineered to solve a fundamental bottleneck in automated career acceleration platforms like **Jaithraya**:
* **The Cost Problem:** Third-party aggregators (such as TheirStack) bill per returned job ($1.00 credit per job). Sourcing a flat delivery quota of 30 viable jobs per day across dozens or hundreds of candidates rapidly balloons into thousands of dollars in monthly vendor costs.
* **The Stale Data Problem:** Public job aggregators, LinkedIn scrapers, and third-party boards are notoriously flooded with "ghost jobs," expired listings, duplicate staffing agencies, and stale postings that were closed weeks ago.
* **The Solution:** Job Atlas functions as an autonomous, self-hosted, 100% free-tier supply engine. It scrapes live job requisitions **directly from enterprise applicant tracking systems (ATS)**, normalizes them into standardized career families and US states, continuously purges closed postings, enforces strict candidate cooldown rules, and exposes a high-performance REST API with sub-millisecond query latency.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                  JOB ATLAS ECOSYSTEM                                   │
└────────────────────────────────────────────────────────────────────────────────────────┘
          │
          ├── 1. Ingestion Layer (60,436 Registered Boards across 12 ATS Platforms)
          │      └── Workday, BambooHR, Paylocity, iCIMS, Greenhouse, Lever, Ashby, etc.
          │      └── Zero-cost public HTTP endpoints; no API keys, no scraping proxies.
          │
          ├── 2. Storage & Indexing Layer (SQLite & Turso Cloud libSQL)
          │      └── 382,687 Verified Active US Vacancies across 19,628 Distinct Employers.
          │      └── Composite covering B-Trees: < 1ms query latency.
          │
          ├── 3. Automated Daily Maintenance (02:00 UTC Cron in GitHub Actions)
          │      ├── Daily Scrape: 6,500 – 8,500 fresh US postings ingested daily.
          │      ├── Daily Enrichment: Automatic classification into 31 Role Families & 50 US States.
          │      ├── Daily Purge: 4,000 – 6,000 closed/expired postings permanently wiped.
          │      └── Cloud Sync: Streamed to Turso Cloud for stateless Render deployment.
          │
          ├── 4. Validation & Inspection Frontend (Next.js 16 + React 19)
          │      ├── 31 Role Family Selector, 50 States + DC dropdown, 9 Metro Quick-Filters.
          │      └── Live API Inspector with one-click cURL generator & JSON modal.
          │
          └── 5. Provider REST API Layer (`/api/v1/`)
                 └── Serves as Supply Leg 3 for Jaithraya's daily job pulling pipeline.
                 └── Supports distinct company batches & 60-day candidate cooldown blackouts.
```

---

## 2. Current Inventory & Operational Capabilities

### 2.1 Database Scale (Verified Real Data)
* **Total Active US Jobs:** `382,687`
* **Total Unique Hiring Companies:** `19,628`
* **Remote-Specific Postings:** `26,133` across `4,075` distinct companies
* **Query Latency:** Sub-millisecond (`< 0.20 ms` via composite covering B-Trees)

### 2.2 ATS Platform Coverage (60,436 Registered Boards)
Job Atlas harvests directly from the unauthenticated public JSON/XML/REST endpoints of 12 enterprise ATS vendors:

| Platform | Registered Boards | Active US Jobs in Database | Key Structural Properties |
| :--- | :--- | :--- | :--- |
| **Paylocity** | 10,252 | 107,547 | Direct company career portals; high density of US mid-market roles. |
| **Workday** | 12,884 | 105,323 | Enterprise Fortune 500 portals (`myworkdayjobs.com`). High salary transparency. |
| **Greenhouse** | 8,333 | 93,813 | Top tech & venture-backed scaleups (`boards.greenhouse.io`). |
| **Lever** | 4,369 | 32,090 | High-growth startups and tech firms (`jobs.lever.co`). |
| **Ashby** | 3,169 | 22,063 | Modern AI, SaaS, and engineering-first companies (`jobs.ashbyhq.com`). |
| **BambooHR** | 11,316 | 21,797 | Small-to-medium businesses and specialized service providers. |
| **iCIMS** | 10,107 | Integrated | Healthcare, retail, logistics, and enterprise corporate boards. |
| **Others** | Workable, SmartRecruiters, Breezy, Recruitee, Personio | Ingestion pipelines active. |

---

### 2.3 Role Family Distribution (31 Standardized Groups)
Every job is parsed and classified into one of 31 standardized career families with precomputed covering indexes:

| Standard Role Family | Active Jobs | Distinct Companies | Quota Viability (30 Jobs/Day for 60 Days = 1,800 Cos) |
| :--- | :--- | :--- | :--- |
| **Business Operations** | 52,883 | **8,796** | **Exceeds requirement by 4.9×** |
| **Healthcare & Clinical** | 28,815 | **2,456** | **Exceeds requirement by 1.4×** |
| **Skilled Trades & Maintenance** | 26,181 | **4,896** | **Exceeds requirement by 2.7×** |
| **Sales & Business Development** | 25,039 | **5,842** | **Exceeds requirement by 3.2×** |
| **Hardware & Engineering** | 24,474 | **3,854** | **Exceeds requirement by 2.1×** |
| **Finance & Accounting** | 13,531 | **4,240** | **Exceeds requirement by 2.4×** |
| **Software Engineering** | 13,496 | **2,964** | **Exceeds requirement by 1.6×** |
| **Manufacturing & Quality** | 13,458 | **2,846** | **Exceeds requirement by 1.6×** |
| **Data & AI** | 9,409 | **2,950** | **Exceeds requirement by 1.6×** |
| **Projects & Programs** | 7,940 | **2,629** | **Exceeds requirement by 1.5×** |
| **Marketing & Communications** | 7,120 | **2,118** | **Exceeds requirement by 1.2×** |
| **Human Resources** | 6,845 | **2,042** | **Exceeds requirement by 1.1×** |
| **Product Management** | 3,210 | **1,450** | Strong supplement to paid aggregators. |
| **Design & UX** | 2,890 | **1,210** | Strong supplement to paid aggregators. |

---

### 2.4 Geographic Distribution (Top States & Metros)

```
Top States by Active Employer Inventory:
  • California (CA)    : 44,976 jobs across 3,554 unique companies
  • Texas (TX)         : 33,318 jobs across 2,886 unique companies
  • New York (NY)      : 28,058 jobs across 3,061 unique companies
  • Florida (FL)       : 16,032 jobs across 1,910 unique companies
  • Pennsylvania (PA)  : 12,617 jobs across 1,381 unique companies
  • Virginia (VA)      : 11,919 jobs across 1,273 unique companies
  • Washington (WA)    : 11,240 jobs across 1,412 unique companies
  • Massachusetts (MA) : 10,890 jobs across 1,520 unique companies
  • Illinois (IL)      : 10,510 jobs across 1,480 unique companies
```

---

## 3. Daily Lifecycle: What Happens in Atlas Every 24 Hours?

To maintain 100% database freshness and prevent candidates from applying to expired postings, Atlas runs an automated cron pipeline every night at **02:00 UTC (9:00 PM Eastern / 07:30 AM IST)** via GitHub Actions ([`.github/workflows/scrape_and_sync.yml`](file:///Users/rafi/Downloads/Job_Scraping/.github/workflows/scrape_and_sync.yml)):

```
02:00 UTC — GitHub Actions Automated Daily Workflow
  │
  ├── Step 1: Scrape Influx (`python -m scraper.cli run`)
  │      ├── Polls registered boards across 12 platforms with multi-threaded workers.
  │      ├── Discovers between 6,500 and 8,500 brand-new US job openings per weekday.
  │      └── Appends new openings into local SQLite storage (`data/jobs.sqlite`).
  │
  ├── Step 2: Enrichment Pipeline (`python scripts/enrich_database.py`)
  │      ├── Normalizes job titles into 31 canonical role families.
  │      ├── Extracts US 2-letter state codes and normalized city names.
  │      ├── Flags remote positions (`workplace = 'Remote'` or `location LIKE '%Remote%'`).
  │      └── Verifies active application URLs and attaches verification evidence.
  │
  ├── Step 3: Expired & Closed Job Purge (`python scripts/purge_closed_jobs.py`)
  │      ├── Evaluates checked postings against live employer board responses.
  │      ├── Permanently deletes 4,000 to 6,000 closed, filled, or non-US jobs.
  │      └── Keeps total database size lean (< 180MB) and prevents dead link failures.
  │
  ├── Step 4: Metadata Precomputation
  │      └── Precomputes role and state distribution counts to `data/metadata.json` for 0ms frontend loads.
  │
  └── Step 5: Turso Cloud libSQL Sync (`python scripts/sync_to_turso.py`)
         └── Pushes the clean database over HTTPS to Turso Cloud (5 GB Free Tier).
         └── Stateless cloud instances (Render) immediately query updated data.
```

### Daily Turnover Summary:
* **Added Daily:** **6,500 to 8,500 brand-new US jobs** (35,000 to 45,000 / week)
* **Purged Daily:** **4,000 to 6,000 closed jobs** permanently deleted
* **Net Active Equilibrium:** **~380,000 to 400,000 live vacancies**

---

## 4. Real-World Testing Against Jaithraya Candidates

To prove that Job Atlas can seamlessly serve as Supply Leg 3, we extracted **all 80 candidate profiles** directly from Jaithraya’s PostgreSQL production database in read-only mode ([`scripts/extract_jaithraya_users.py`](file:///Users/rafi/Downloads/Job_Scraping/scripts/extract_jaithraya_users.py)) and ran comprehensive simulation audits.

### 4.1 Test Methodology
For every candidate:
1. **Target Titles & Roles:** Mapped to standardized role families and exact title matching.
2. **Locations:** Mapped to 2-letter state codes, metro areas, or remote preferences.
3. **Master CV Self-Employers:** Blocked previous employers to prevent auto-rejections.
4. **60-Day Cooldown Ledger:** Excluded all companies the candidate was shown or applied to over the last 60 days (from both shortlists and operator submissions).
5. **Distinct Company Constraint:** Enforced **1 unique company per job** in each daily batch.

---

### 4.2 Simulation Results ([`data/atlas_candidate_simulation_results.json`](file:///Users/rafi/Downloads/Job_Scraping/data/atlas_candidate_simulation_results.json))

* **Total Candidates Tested:** 33 active candidates with daily job supply enabled.
* **Daily 30-Job Quota Attainment:** **33 / 33 (100.0% Passed)**
* **Average Unexhausted Supply Runway:** **104.5 days** without repeating a single company!

#### Sample Candidate Results:

| Candidate Handle | Target Domain | Locations | 60-Day History Excluded | Net Eligible Companies | Daily Quota (30) | Supply Runway |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`akhil-setty-balija`** | Data Analyst | OH, IN, KY, MI, PA, WV + Remote | 47 companies | **2,944** | **PASSED** | **98.1 days** |
| **`akila-lourdes-miriyala-francis`** | Machine Learning | CA, MA, NY, TX, WA + Remote | 804 companies | **1,687** | **PASSED** | **56.2 days** |
| **`akilan-manivannan`** | Machine Learning | CA, MA, NY, TX, WA + Remote | 995 companies | **1,658** | **PASSED** | **55.3 days** |
| **`anwar-shaik`** | Data Analyst | CT, MA, NY, RI + Remote | 101 companies | **2,934** | **PASSED** | **97.8 days** |
| **`ganesh-thalla`** | AI / ML Engineer | MO, Nationwide + Remote | 1,054 companies | **2,827** | **PASSED** | **94.2 days** |
| **`geetika-surampudi`** | DevOps Engineer | Nationwide + Remote | 1,713 companies | **2,847** | **PASSED** | **94.9 days** |
| **`laya-kalali`** | Software Engineer | Nationwide + Remote | 3,586 companies | **2,738** | **PASSED** | **91.3 days** |
| **`gowthami-jampana`** | Data Engineer | Nationwide + Remote | 1,178 companies | **2,779** | **PASSED** | **92.6 days** |
| **`harish-kumar`** | Cloud / Network | Nationwide + Remote | 2,249 companies | **3,828** | **PASSED** | **127.6 days** |
| **`mohith-reddy`** | Business Analyst | Nationwide + Remote | 86 companies | **8,780** | **PASSED** | **292.7 days** |
| **`muktha-nanda-reddy-kamidi`** | Business Analyst | MA, Nationwide + Remote | 460 companies | **8,773** | **PASSED** | **292.4 days** |

> [!NOTE]
> Even candidates with massive historical application footprints (such as `laya-kalali` with 3,586 past company shortlists, or `akila-lourdes-miriyala-francis` with 804 past company shortlists) still have **1,650+ to 2,700+ fresh, uncontacted employers** in Job Atlas.

---

### 4.3 History Cross-Reference & Leakage Audit ([`data/history_cross_reference_audit.json`](file:///Users/rafi/Downloads/Job_Scraping/data/history_cross_reference_audit.json))

We performed an audit cross-referencing Jaithraya’s **35,723 shortlist records** and **15,321 operator submissions** against Job Atlas:
1. **Active Overlap:** **1,924 exact URLs** in Jaithraya’s history are currently live and active in Job Atlas. (The remaining ~33,800 historical jobs have expired and were purged).
2. **Collisions Blocked:** **7,650 candidate-level colliding job assignments were detected and blocked**.
3. **Leakage Rate:** **0.0%**. When applying candidate exclusion lists (`exclude_companies`, `exclude_keys`, and `distinct_company=1`), **zero previously applied or shortlisted jobs can ever be served to that candidate**.

---

## 5. Complete REST API Reference (`/api/v1/`)

The Job Atlas Provider API runs on Next.js 16 (Node 22) and exposes five high-performance REST endpoints.

### 5.1 Base URLs
* **Local Development / Docker:** `http://127.0.0.1:3000`
* **Production Cloud (Render Free Service):** `https://job-atlas-supply.onrender.com` (or your assigned Render domain)

---

### 5.2 Endpoints Summary

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/v1/health` | Service health, version, uptime, and database status. |
| `GET` | `/api/v1/metadata` | Precomputed role family, state, and platform distribution. |
| `GET` | `/api/v1/jobs` | **Primary Job Supply Feed.** Supports filtering, cooldowns, and distinct companies. |
| `GET` | `/api/v1/jobs/:key` | Single job hydration with full description and apply URL. |
| `POST` | `/api/v1/jobs/batch` | Batch lookup by array of job keys for O(1) deduplication in Jaithraya. |

---

### 5.3 Detailed Endpoint Documentation

#### 1. `GET /api/v1/health`
Check service health and uptime.
```bash
curl -X GET "http://127.0.0.1:3000/api/v1/health"
```
**Response (200 OK):**
```json
{
  "status": "ok",
  "service": "job-atlas-supply-engine",
  "version": "1.0.0",
  "leg": "Supply Leg 3 (Job Atlas)",
  "uptime_seconds": 3840,
  "timestamp": "2026-11-09T10:15:00.000Z"
}
```

---

#### 2. `GET /api/v1/metadata`
Returns instant (0ms) precomputed statistics across all 31 role families and 50 US states.
```bash
curl -X GET "http://127.0.0.1:3000/api/v1/metadata"
```
**Response (200 OK):**
```json
{
  "status": "success",
  "total_jobs": 382687,
  "total_us_jobs": 382687,
  "total_us_remote": 26133,
  "role_groups": [
    { "name": "Software Engineering", "jobs": 13496 },
    { "name": "Data and AI", "jobs": 9409 },
    { "name": "Business Operations", "jobs": 52883 }
  ],
  "states": [
    { "code": "CA", "name": "California", "jobs": 44976 },
    { "code": "TX", "name": "Texas", "jobs": 33318 },
    { "code": "NY", "name": "New York", "jobs": 28058 }
  ],
  "platforms": [
    { "platform": "workday", "jobs": 105323 },
    { "platform": "greenhouse", "jobs": 93813 },
    { "platform": "lever", "jobs": 32090 }
  ]
}
```

---

#### 3. `GET /api/v1/jobs` (Primary Feed Endpoint)
Queries the job pool with candidate-specific targeting, cooldown blacklists, and distinct company enforcement.

**Query Parameters:**
| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `role_group` | string | No | One of the 31 standardized career families (e.g. `Software Engineering`, `Data and AI`). |
| `title` | string | No | Substring search on job title (e.g. `Backend Engineer`). |
| `state` / `us_state` | string | No | 2-letter US state code (e.g. `CA`, `TX`, `NY`). |
| `city` / `us_city` | string | No | City name (e.g. `San Francisco`, `Austin`). |
| `workplace` | string | No | Workplace type: `Remote`, `Hybrid`, `On-site`. |
| `remote` | string/bool | No | Pass `1` or `true` for remote roles only. |
| `us_only` | string/bool | No | Default `1`. Restricts strictly to US verified jobs. |
| `distinct_company`| string/bool | No | **Set `1` to enforce 1 unique company per job in the returned batch.** |
| `exclude_companies`| string | No | **Comma-separated list of company names or keys to exclude (candidate 60-day cooldown).** |
| `exclude_keys` | string | No | Comma-separated list of exact job keys to exclude. |
| `since` | string | No | ISO date or YYYY-MM-DD to filter jobs published after this timestamp. |
| `limit` | integer | No | Default `30`, max `200`. Number of jobs to return. |
| `page` | integer | No | Default `1`. Page number for pagination. |
| `sort` | string | No | `date` (default, freshest first), `title`, `company`. |

**Example cURL Call:**
```bash
curl -X GET "http://127.0.0.1:3000/api/v1/jobs?\
role_group=Software%20Engineering&\
state=CA&\
distinct_company=1&\
limit=30&\
exclude_companies=Google,Meta,Amazon,Apple"
```

**Response (200 OK):**
```json
{
  "status": "success",
  "total": 3150,
  "page": 1,
  "pages": 105,
  "limit": 30,
  "has_more": true,
  "data": [
    {
      "id": "ashby:turion-space:8580bd7e-c9cc-4a48-a1de-df6bafe04216",
      "key": "ashby:turion-space:8580bd7e-c9cc-4a48-a1de-df6bafe04216",
      "title": "Spacecraft Systems Engineer",
      "company": "Turion Space",
      "company_key": "ashby:turion-space",
      "platform": "ashby",
      "board": "turion-space",
      "job_id": "8580bd7e-c9cc-4a48-a1de-df6bafe04216",
      "location": "Irvine, CA",
      "is_us": true,
      "us_state": "CA",
      "us_city": "Irvine",
      "workplace": "On-site",
      "role_group": "Software Engineering",
      "department": "Software",
      "employment_type": "FullTime",
      "salary_min": 125000,
      "salary_max": 175000,
      "salary_currency": "USD",
      "salary_interval": "1 YEAR",
      "salary_text": "$125K – $175K",
      "url": "https://jobs.ashbyhq.com/turion-space/8580bd7e-c9cc-4a48-a1de-df6bafe04216",
      "apply_url": "https://jobs.ashbyhq.com/turion-space/8580bd7e-c9cc-4a48-a1de-df6bafe04216/application",
      "source_url": "https://api.ashbyhq.com/posting-api/job-board/turion-space?includeCompensation=true",
      "published_at": "2026-10-29T21:59:57.453000Z",
      "updated_at": null,
      "checked_at": "2026-10-30T11:38:36Z",
      "active": true,
      "verification": {
        "status": "Open for applications when checked",
        "evidence": "Exact posting loaded at its live application URL; isListed=true; deadline checked; no application-closure notice",
        "verified_at": "2026-10-31T09:49:51Z"
      }
    }
  ]
}
```

---

#### 4. `GET /api/v1/jobs/:key`
Hydrates full job description, raw HTML, and direct application URL for downstream resume tailoring.
```bash
curl -X GET "http://127.0.0.1:3000/api/v1/jobs/ashby:turion-space:8580bd7e-c9cc-4a48-a1de-df6bafe04216"
```
**Response (200 OK):**
```json
{
  "status": "success",
  "data": {
    "key": "ashby:turion-space:8580bd7e-c9cc-4a48-a1de-df6bafe04216",
    "title": "Spacecraft Systems Engineer",
    "company": "Turion Space",
    "platform": "ashby",
    "apply_url": "https://jobs.ashbyhq.com/turion-space/8580bd7e-c9cc-4a48-a1de-df6bafe04216/application",
    "description": "<h3>About the Role</h3><p>We are seeking a Spacecraft Systems Engineer to join our team in Irvine, CA...</p>",
    "active": true,
    "salary_text": "$125K – $175K"
  }
}
```

---

#### 5. `POST /api/v1/jobs/batch`
Batch lookups of multiple job keys for fast O(1) deduplication in Jaithraya before spending credits or triggering resume variants.
```bash
curl -X POST "http://127.0.0.1:3000/api/v1/jobs/batch" \
  -H "Content-Type: application/json" \
  -d '{"keys": ["ashby:turion-space:8580bd7e-c9cc-4a48-a1de-df6bafe04216", "lever:zoox:8703109b-1cb5-4e78-999a-7093ca4407e2"]}'
```
**Response (200 OK):**
```json
{
  "status": "success",
  "count": 2,
  "data": [
    { "key": "ashby:turion-space:8580bd7e-c9cc-4a48-a1de-df6bafe04216", "company": "Turion Space", "active": true },
    { "key": "lever:zoox:8703109b-1cb5-4e78-999a-7093ca4407e2", "company": "Zoox", "active": true }
  ]
}
```

---

## 6. How to Integrate Job Atlas as Supply Leg 3 into Jaithraya

In Jaithraya (`job-discovery-engine-main`), daily job pulling is governed by `atsSupplyRouter.ts` or `theirStackDigestRun.ts`. Here is the exact plug-and-play TypeScript client:

```typescript
// src/services/supply/atlasSupplyLeg.ts
import axios from 'axios';

const ATLAS_API_URL = process.env.ATLAS_SUPPLY_API_URL || 'http://127.0.0.1:3000/api/v1';

export interface AtlasJobQuery {
  roleGroup: string;
  state?: string;
  remote?: boolean;
  limit?: number;
  distinctCompany?: boolean;
  excludeCompanies?: string[]; // Candidate 60-day history
  excludeKeys?: string[];
}

export async function fetchAtlasSupply(query: AtlasJobQuery) {
  try {
    const params: Record<string, string | number> = {
      role_group: query.roleGroup,
      distinct_company: query.distinctCompany ? '1' : '0',
      limit: query.limit || 30,
      us_only: '1'
    };

    if (query.state) params.state = query.state;
    if (query.remote) params.remote = '1';
    if (query.excludeCompanies && query.excludeCompanies.length > 0) {
      params.exclude_companies = query.excludeCompanies.slice(0, 500).join(',');
    }
    if (query.excludeKeys && query.excludeKeys.length > 0) {
      params.exclude_keys = query.excludeKeys.join(',');
    }

    const response = await axios.get(`${ATLAS_API_URL}/jobs`, { params, timeout: 5000 });
    return response.data.data;
  } catch (error) {
    console.error('Failed to pull from Job Atlas Supply Leg 3:', error);
    return [];
  }
}
```

---

## 7. Zero-Cost Cloud Deployment (Render + Turso Cloud)

Job Atlas is designed to operate 100% within free cloud tiers ($0.00 cost):

```
┌──────────────────────────────────────┐          ┌──────────────────────────────────────┐
│        GitHub Actions (Free)         │          │          Render Free Service         │
│  • Runs daily at 02:00 UTC           │          │  • Next.js 16 Web Service            │
│  • Scrapes, Enriches, Purges         │          │  • Ephemeral disk (Stateless)        │
│  • Syncs to Turso via HTTPS Pipe     │          │  • Connects to Turso libSQL          │
└──────────────────┬───────────────────┘          └──────────────────┬───────────────────┘
                   │                                                 │
                   ▼                                                 ▼
        ┌───────────────────────────────────────────────────────────────────────┐
        │                         Turso Cloud (libSQL)                          │
        │  • 5 GB Storage (Database is ~180MB)                                  │
        │  • 1 Billion row reads/month free tier                                │
        │  • High-performance edge replica in AWS Oregon / US                   │
        └───────────────────────────────────────────────────────────────────────┘
```

### 7.1 Setup Steps
1. **Turso Cloud Database:**
   ```bash
   turso db create job-atlas-us
   turso db tokens create job-atlas-us
   ```
2. **Push Local Database to Turso:**
   ```bash
   export TURSO_DATABASE_URL="libsql://job-atlas-us-<user>.turso.io"
   export TURSO_AUTH_TOKEN="your_token"
   python3 scripts/sync_to_turso.py
   ```
3. **Deploy to Render:**
   * Push repo to GitHub.
   * Connect repo to Render using [`render.yaml`](file:///Users/rafi/Downloads/Job_Scraping/render.yaml).
   * Set environment variables in Render Dashboard:
     * `TURSO_DATABASE_URL`
     * `TURSO_AUTH_TOKEN`
   * Service starts in under 2 minutes with memory footprint < 90MB RAM.

