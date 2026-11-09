# Job Atlas

A local job collector and Next.js workspace built from the public-feed patterns and employer discovery lists in [freehire](https://github.com/strelov1/freehire), [job-board-aggregator](https://github.com/Riley-Dorrington/job-board-aggregator), and [job-boards](https://github.com/mherzog4/job-boards).

The collector reads employer feeds directly. The frontend searches the resulting local SQLite database, so the full collection is never downloaded into the browser.

## Start locally

Requires Node.js 22.13+ and Python 3.10+. Node's built-in SQLite module is used by the Next.js server.

```sh
npm install
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
python3 scripts/setup_sources.py
cp .env.example .env
```

Set `JOB_SCRAPER_CONTACT` in `.env` to your real contact email. The address identifies requests to feed operators and is not exposed to the frontend. It is already configured in this local workspace.

```sh
npm run dev
```

Open http://127.0.0.1:3000. For a production build, use `npm run build` followed by `npm start`.

## Collect jobs

```sh
# Smoke test: sample every supported platform.
.venv/bin/python -m scraper.cli scrape --limit 24

# Full run over the combined employer registry.
.venv/bin/python -m scraper.cli scrape

# Resume a gracefully interrupted run.
.venv/bin/python -m scraper.cli scrape --resume

# Collect particular platforms or an exact board identifier.
.venv/bin/python -m scraper.cli scrape --platforms ashby,greenhouse,lever
.venv/bin/python -m scraper.cli scrape --platforms ashby --board openai

# Regenerate CSV snapshots from the local database.
.venv/bin/python -m scraper.cli export
.venv/bin/python -m scraper.cli export --include-descriptions
```

The network worker cap is eight. Requests use reusable connections, finite timeouts, bounded retries, and host-wide backoff after rate limits. There are no proxy or access-control bypasses. A full run can take a considerable time because Workday requires paginated requests and many historical board identifiers are invalid. Control-C saves completed boards and finishes in-flight requests before exiting. Only one collector runs at a time.

Supported adapters: Greenhouse, Ashby, Lever (US and EU), BambooHR, Workday, Paylocity, iCIMS, Workable, Recruitee, SmartRecruiters, Personio, and Breezy. Most discovery coverage comes from job-board-aggregator's seven platform lists. job-boards supplies additional curated seeds. Freehire's current full catalog lives in its production database and is not distributed in the clone; its public adapter examples supply only a small number of extra candidates. This project does not claim to run all of Freehire's adapters or reproduce its entire catalog.

## Files

- `outputs/job-atlas/all_jobs.csv`: one combined UTF-8 CSV, readable by Excel.
- `outputs/job-atlas/company_csvs.zip`: one CSV per company feed.
- `outputs/job-atlas/companies.csv`: company-to-file index with job counts.
- `outputs/job-atlas/company_workbooks.zip`: Excel volumes, each with an Index and individual company sheets.
- `outputs/job-atlas/collection_log.csv`: every attempted board and its outcome.
- `outputs/job-atlas/manifest.json`: snapshot totals, field definitions, and limitations.
- `data/jobs.sqlite`: normalized records, available descriptions, a full-text index, board results, and run history.
- `data/progress.json`: latest collection progress, shown in the frontend.

A CSV cannot contain worksheets. Excel volumes provide the requested company sheets without creating an impractical workbook with thousands of tabs. Company identifiers are `platform:tenant`; the same employer's accounts on separate platforms remain separate when their identity cannot be established reliably. Workday requisitions are deduplicated across sites under the same tenant.

### Excel export

Workbooks are authored with Codex's bundled `@oai/artifact-tool`, linked under `workbook/node_modules` in this workspace. Use the bundled Node executable when building them here:

```sh
/Users/rafi/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node workbook/build.mjs --resume
python3 scripts/package_workbooks.py
```

The builder isolates each volume in its own process, supports resuming, and checks content signatures before reusing a volume. It creates up to 150 company sheets or 15,000 jobs per volume, except when a single company itself exceeds that row budget. `WORKBOOK_MAX_SHEETS` and `WORKBOOK_MAX_ROWS` can adjust those limits. The packager checks every sheet name and job row count against the CSV manifest before creating the final archive.

## Frontend

- Full-text keyword search, location, platform, company, and work-arrangement filters.
- Server-side pagination and sorting across the full local database.
- Bookmarks stored only in this browser, up to 500 jobs.
- Employer links, available descriptions, and original feed URLs.
- Company discovery, source coverage, and collection progress.
- Filtered CSV downloads streamed from SQLite, plus snapshot downloads.
- URL-synchronized explorer filters and responsive layouts.

The server binds to `127.0.0.1`. No cloud database, API key, account, or deployment is required. Saved jobs are browser-local; changing browsers or clearing site data removes the shortlist.

## Data meaning and quality

“Listed” means the job was present in an employer's public feed or sitemap at `checked_at`. It does not guarantee that the employer is reviewing applications, or that every application endpoint is functioning. Old posting dates can belong to active evergreen requisitions. No age cutoff is imposed because the goal is broad coverage.

The separate **application-verified US export** in `outputs/united_states/active_only/` uses a stricter rule. `python3 scripts/verify_active_jobs.py` freshly checks each delivered US job's application page or job-specific application API. It requires an exact posting plus an application form/schema or an explicit open/can-apply status, and checks the current US location. General applications, talent pools, evergreen posts, expired deadlines, closed roles and inconclusive checks are excluded. Each retained row records its verification time, URL and evidence. This checks availability without submitting applications. Use `--resume` to continue the same snapshot after interruption; results older than six hours are checked again. `--resume --retry-unconfirmed` retries inconclusive checks. The role workbook is built from this filtered CSV, rather than the collector's broad `active` flag.

`scripts/finish_active_delivery.py` waits for those checks, verifies the filtered export, builds the role workbook, and then creates the root `companies/` folder with one CSV per company name. It also creates `companies.zip` and `companies_index.csv` in `outputs/united_states/active_only/`. Every company row retains all verification fields, and the export checks every field against the filtered master CSV.

Missing salaries, locations, employment types, and dates remain blank. A location with no explicit work-mode information is “Not specified,” rather than guessed to be on-site. Greenhouse's modification time is kept as `updated_at`, not presented as a posting date. Workday's relative date is kept verbatim in `date_note`. iCIMS sitemap titles are derived from URL text, and individual job pages are not all checked. Full descriptions are fetched only when returned by the listing feed; they stay in SQLite unless explicitly included in the CSV export.

Only a fully successful board fetch can retire absent jobs. A partial or failed board keeps prior observations with their original check times. Successful later fetches update observed jobs and preserve `first_seen`. Posting keys are namespaced by platform and board; cross-platform requisitions are not deduplicated by guessing from similar titles. Spreadsheet formula-like text is escaped in exports.

## Validation

```sh
python3 -m unittest discover -s tests -v
npm run typecheck
npm run build
```

Tests cover lifecycle handling, partial pagination, key collisions, unlisted jobs, missing-data semantics, timestamp conversion, unsafe URLs, and CSV/archive reconciliation. Workbook counts and worksheet names are checked again after export. Representative workbook layouts and the frontend are visually reviewed; these checks do not constitute a manual review of every job or a test in the desktop Excel application.

## Attribution and licenses

Reference code is MIT-licensed; the original repositories and their license files are retained under `sources/`. Exact local revisions are recorded in `source_versions.json`. This implementation is separate from their full application stacks.

The curated company datasets in Riley-Dorrington's project are [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/). This derived registry and collection are intended for noncommercial use. Obtain the dataset owner's permission before using those lists commercially. Employer postings remain their owners' content.
