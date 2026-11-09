"use client";

import { useEffect, useRef, useState } from "react";
import {
  ArrowDownToLine, ArrowLeft, ArrowRight, ArrowUpRight, Bookmark, Check,
  ChevronDown, ChevronLeft, ChevronRight, CircleHelp, Code2, Copy,
  Database, ExternalLink, FileSpreadsheet, FolderDown, Globe2, Layers3,
  LayoutGrid, MapPin, Menu, Play, RefreshCw, Search, ShieldCheck,
  SlidersHorizontal, Sparkles, Sprout, Terminal, X
} from "lucide-react";
import type { Company, Filters, Job, Metadata, Results, Stats } from "@/lib/data";

type View = "explore" | "saved" | "companies" | "sources" | "exports" | "api";
type Downloads = { csv: boolean; company_csvs: boolean; xlsx: boolean; workbooks: boolean };

const labels: Record<string, string> = {
  greenhouse: "Greenhouse", ashby: "Ashby", lever: "Lever", bamboohr: "BambooHR",
  workday: "Workday", paylocity: "Paylocity", icims: "iCIMS", workable: "Workable",
  recruitee: "Recruitee", smartrecruiters: "SmartRecruiters", personio: "Personio", breezy: "Breezy"
};

const US_STATES = [
  { code: "AL", name: "Alabama" }, { code: "AK", name: "Alaska" }, { code: "AZ", name: "Arizona" },
  { code: "AR", name: "Arkansas" }, { code: "CA", name: "California" }, { code: "CO", name: "Colorado" },
  { code: "CT", name: "Connecticut" }, { code: "DE", name: "Delaware" }, { code: "FL", name: "Florida" },
  { code: "GA", name: "Georgia" }, { code: "HI", name: "Hawaii" }, { code: "ID", name: "Idaho" },
  { code: "IL", name: "Illinois" }, { code: "IN", name: "Indiana" }, { code: "IA", name: "Iowa" },
  { code: "KS", name: "Kansas" }, { code: "KY", name: "Kentucky" }, { code: "LA", name: "Louisiana" },
  { code: "ME", name: "Maine" }, { code: "MD", name: "Maryland" }, { code: "MA", name: "Massachusetts" },
  { code: "MI", name: "Michigan" }, { code: "MN", name: "Minnesota" }, { code: "MS", name: "Mississippi" },
  { code: "MO", name: "Missouri" }, { code: "MT", name: "Montana" }, { code: "NE", name: "Nebraska" },
  { code: "NV", name: "Nevada" }, { code: "NH", name: "New Hampshire" }, { code: "NJ", name: "New Jersey" },
  { code: "NM", name: "New Mexico" }, { code: "NY", name: "New York" }, { code: "NC", name: "North Carolina" },
  { code: "ND", name: "North Dakota" }, { code: "OH", name: "Ohio" }, { code: "OK", name: "Oklahoma" },
  { code: "OR", name: "Oregon" }, { code: "PA", name: "Pennsylvania" }, { code: "RI", name: "Rhode Island" },
  { code: "SC", name: "South Carolina" }, { code: "SD", name: "South Dakota" }, { code: "TN", name: "Tennessee" },
  { code: "TX", name: "Texas" }, { code: "UT", name: "Utah" }, { code: "VT", name: "Vermont" },
  { code: "VA", name: "Virginia" }, { code: "WA", name: "Washington" }, { code: "WV", name: "West Virginia" },
  { code: "WI", name: "Wisconsin" }, { code: "WY", name: "Wyoming" }, { code: "DC", name: "District of Columbia" }
];

const METROS = [
  { label: "SF Bay Area", city: "San Francisco", state: "CA" },
  { label: "NYC Metro", city: "New York", state: "NY" },
  { label: "Seattle", city: "Seattle", state: "WA" },
  { label: "Austin", city: "Austin", state: "TX" },
  { label: "Boston", city: "Boston", state: "MA" },
  { label: "Chicago", city: "Chicago", state: "IL" },
  { label: "Los Angeles", city: "Los Angeles", state: "CA" },
  { label: "Denver", city: "Denver", state: "CO" },
  { label: "Atlanta", city: "Atlanta", state: "GA" }
];

const number = (value: number) => value.toLocaleString("en-IN");
const compact = (value: number) => Intl.NumberFormat("en", {notation: "compact", maximumFractionDigits: 1}).format(value);
function initial(name: string) { return name.replace(/[^\p{L}\p{N}\s]/gu, "").split(/\s+/).filter(Boolean).map(x => x[0]).slice(0, 2).join("").toUpperCase() || "J"; }
function color(name: string) { return ["sage", "peach", "lilac", "blue", "sand"][Array.from(name).reduce((a, c) => a + c.charCodeAt(0), 0) % 5]; }
function formatDate(value: string) { if (!value) return "Not supplied"; const date = new Date(value); return Number.isNaN(date.valueOf()) ? "Not supplied" : date.toLocaleDateString("en-US", {day: "numeric", month: "short", year: "numeric"}); }

function salary(j: Job) {
  if (j.salary_min == null && j.salary_max == null) return j.salary_text || "";
  return `${j.salary_currency || "$"} ${j.salary_min == null ? "" : compact(j.salary_min)}${j.salary_min != null && j.salary_max != null ? " – " : ""}${j.salary_max == null ? "+" : compact(j.salary_max)}${j.salary_interval ? ` / ${j.salary_interval}` : ""}`.trim();
}

export default function Dashboard({
  initialResults,
  initialStats,
  initialCompanies,
  initialMetadata,
  downloads: initialDownloads
}: {
  initialResults: Results;
  initialStats: Stats;
  initialCompanies: Company[];
  initialMetadata?: Metadata;
  downloads: Downloads;
}) {
  const [view, setView] = useState<View>("explore");
  const [filters, setFilters] = useState<Filters>({ us_only: "1" });
  const [results, setResults] = useState(initialResults);
  const [stats, setStats] = useState(initialStats);
  const [metadata, setMetadata] = useState<Metadata | undefined>(initialMetadata);
  const [companies, setCompanies] = useState(initialCompanies);
  const [companySearch, setCompanySearch] = useState("");
  const [downloads, setDownloads] = useState(initialDownloads);
  const [saved, setSaved] = useState<string[]>([]);
  const [savedReady, setSavedReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<Job | null>(null);
  const [detailBusy, setDetailBusy] = useState(false);
  const [mobileNav, setMobileNav] = useState(false);
  const [toast, setToast] = useState("");
  const [refresh, setRefresh] = useState(0);
  const [apiModalOpen, setApiModalOpen] = useState(false);
  const [apiResponseJson, setApiResponseJson] = useState("");
  const [apiLoading, setApiLoading] = useState(false);

  const closeRef = useRef<HTMLButtonElement>(null);
  const detailsRequest = useRef(0);
  const mounted = useRef(false);

  useEffect(() => {
    try {
      const data = JSON.parse(localStorage.getItem("job-atlas-saved") || "[]");
      if (Array.isArray(data)) setSaved(data.filter(x => typeof x === "string").slice(0, 500));
    } catch {}
    setSavedReady(true);
    const url = new URLSearchParams(window.location.search);
    const next: Filters = { us_only: "1" };
    for (const key of [
      "q", "location", "platform", "company", "workplace", "sort", "page",
      "role_group", "state", "city", "remote", "us_only", "active_only"
    ] as const) {
      if (url.get(key) !== null) next[key] = url.get(key)!;
    }
    setFilters(next);
    if (["saved", "companies", "sources", "exports", "api"].includes(url.get("view") || "")) {
      setView(url.get("view") as View);
    }
  }, []);

  useEffect(() => {
    if (savedReady) localStorage.setItem("job-atlas-saved", JSON.stringify(saved));
  }, [saved, savedReady]);

  // Debounced job search
  useEffect(() => {
    const controller = new AbortController();
    if (!mounted.current) {
      mounted.current = true;
      return () => controller.abort();
    }
    if (view !== "explore" && view !== "saved") return;

    const timer = setTimeout(async () => {
      setBusy(true);
      setError("");
      const params = new URLSearchParams();
      Object.entries(filters).forEach(([k, v]) => {
        if (v !== undefined && v !== "") params.set(k, String(v));
      });
      const publicParams = new URLSearchParams(params);
      if (view === "saved") {
        params.set("saved", JSON.stringify(saved));
        publicParams.set("view", "saved");
      }
      window.history.replaceState(null, "", publicParams.size ? `?${publicParams}` : window.location.pathname);
      try {
        const response = await fetch(`/api/jobs?${params}`, { signal: controller.signal });
        if (!response.ok) throw new Error("Jobs could not be loaded. Try refreshing the results.");
        setResults(await response.json());
      } catch (e) {
        if (!controller.signal.aborted) setError(e instanceof Error ? e.message : "Jobs could not be loaded.");
      } finally {
        if (!controller.signal.aborted) setBusy(false);
      }
    }, 220);

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [filters, view, saved, refresh]);

  // Companies search
  useEffect(() => {
    if (view !== "companies") return;
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      try {
        const r = await fetch(`/api/companies?q=${encodeURIComponent(companySearch)}`, { signal: controller.signal });
        if (!r.ok) throw new Error();
        setCompanies(await r.json());
      } catch {
        if (!controller.signal.aborted) setError("Company list could not be loaded.");
      }
    }, 200);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [companySearch, view]);

  // Metadata & stats polling
  useEffect(() => {
    const update = async () => {
      try {
        const [statsRes, metaRes] = await Promise.all([
          fetch("/api/stats"),
          fetch("/api/v1/metadata")
        ]);
        if (statsRes.ok) {
          const data = await statsRes.json();
          setStats(data);
          setDownloads(data.downloads);
          if (data.progress?.status === "running") setRefresh(x => x + 1);
        }
        if (metaRes.ok) {
          setMetadata(await metaRes.json());
        }
      } catch {}
    };
    const id = setInterval(update, 25000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    if (!toast) return;
    const id = setTimeout(() => setToast(""), 2500);
    return () => clearTimeout(id);
  }, [toast]);

  // Modal key handling
  useEffect(() => {
    if (!selected && !apiModalOpen) return;
    const oldFocus = document.activeElement as HTMLElement | null;
    const before = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeRef.current?.focus();
    const key = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        detailsRequest.current++;
        setSelected(null);
        setApiModalOpen(false);
      }
    };
    document.addEventListener("keydown", key);
    return () => {
      document.body.style.overflow = before;
      document.removeEventListener("keydown", key);
      oldFocus?.focus();
    };
  }, [selected?.key, apiModalOpen]);

  function update(key: keyof Filters, value: string | boolean) {
    setFilters(f => ({ ...f, [key]: value, page: "1" }));
  }

  function toggleMetro(metro: { city: string; state: string }) {
    if (filters.state === metro.state && filters.city === metro.city) {
      setFilters(f => ({ ...f, state: "", city: "", page: "1" }));
    } else {
      setFilters(f => ({ ...f, state: metro.state, city: metro.city, page: "1" }));
    }
  }

  function navigate(next: View) {
    setView(next);
    setMobileNav(false);
    setError("");
    if (next !== "explore" && next !== "saved") {
      window.history.replaceState(null, "", `?view=${next}`);
    }
  }

  function toggleSave(job: Job) {
    if (saved.includes(job.key)) {
      setSaved(s => s.filter(k => k !== job.key));
      setToast("Removed from saved jobs");
    } else if (saved.length >= 500) {
      setToast("You have 500 saved jobs. Remove one to save another.");
    } else {
      setSaved(s => [...s, job.key]);
      setToast("Job saved to your workspace");
    }
  }

  async function openJob(job: Job) {
    setSelected(job);
    setDetailBusy(true);
    const requestId = ++detailsRequest.current;
    try {
      const response = await fetch(`/api/v1/jobs/${encodeURIComponent(job.key)}`);
      if (!response.ok) throw new Error("This job is no longer active in the collection.");
      const full = await response.json();
      if (requestId === detailsRequest.current && full.data) setSelected(full.data);
    } catch (e) {
      if (requestId === detailsRequest.current) setToast(e instanceof Error ? e.message : "Could not load details");
    } finally {
      if (requestId === detailsRequest.current) setDetailBusy(false);
    }
  }

  function buildApiUrl() {
    const params = new URLSearchParams();
    if (filters.q) params.set("q", filters.q);
    if (filters.role_group) params.set("role_group", filters.role_group);
    if (filters.state) params.set("state", filters.state);
    if (filters.city) params.set("city", filters.city);
    if (filters.workplace) params.set("workplace", filters.workplace);
    if (filters.platform) params.set("platform", filters.platform);
    if (filters.remote === "1" || filters.remote === true || filters.remote === "true") params.set("remote", "1");
    if (filters.active_only === "1" || filters.active_only === true || filters.active_only === "true") params.set("active_only", "1");
    params.set("limit", "30");
    return `/api/v1/jobs?${params.toString()}`;
  }

  async function testApiCall() {
    setApiLoading(true);
    setApiModalOpen(true);
    try {
      const url = buildApiUrl();
      const res = await fetch(url);
      const data = await res.json();
      setApiResponseJson(JSON.stringify(data, null, 2));
    } catch (err) {
      setApiResponseJson(JSON.stringify({ error: err instanceof Error ? err.message : "Request failed" }, null, 2));
    } finally {
      setApiLoading(false);
    }
  }

  function copyCurlCommand() {
    const origin = typeof window !== "undefined" ? window.location.origin : "http://127.0.0.1:3000";
    const curl = `curl -s "${origin}${buildApiUrl()}"`;
    navigator.clipboard.writeText(curl);
    setToast("cURL command copied to clipboard!");
  }

  function exportUrl() {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([k, v]) => {
      if (v !== undefined && v !== "" && k !== "page") params.set(k, String(v));
    });
    if (view === "saved") params.set("saved", JSON.stringify(saved));
    return `/api/export?${params}`;
  }

  const activeFilters = [
    "q", "location", "platform", "company", "workplace", "role_group", "state", "city"
  ].filter(k => filters[k as keyof Filters]);

  const isJobs = view === "explore" || view === "saved";
  const running = stats.progress?.status === "running";
  const roleGroups = metadata?.role_groups || [];

  return (
    <div className="workspace">
      <a className="skip-link" href="#main">Skip to content</a>
      {mobileNav && <button className="nav-scrim" aria-label="Close navigation" onClick={() => setMobileNav(false)} />}

      <aside id="workspace-navigation" className={`sidebar ${mobileNav ? "is-open" : ""}`}>
        <a href="/" className="brand" aria-label="Job Atlas home">
          <span className="brand-symbol"><Layers3 size={23} strokeWidth={1.7} /></span>
          <span>job atlas<span className="brand-period">.</span></span>
        </a>
        <div className="workspace-label">
          <span className="workspace-dot" /> JAITHRAYA SUPPLY ENGINE
        </div>

        <nav aria-label="Main navigation">
          <div className="nav-caption">DISCOVER & VALIDATE</div>
          <button className={`nav-item ${view === "explore" ? "active" : ""}`} onClick={() => navigate("explore")}>
            <Globe2 size={19} /> Explore jobs <span className="nav-arrow"><ArrowUpRight size={15} /></span>
          </button>
          <button className={`nav-item ${view === "api" ? "active" : ""}`} onClick={() => navigate("api")}>
            <Terminal size={19} /> API playground <span className="nav-count">v1</span>
          </button>
          <button className={`nav-item ${view === "companies" ? "active" : ""}`} onClick={() => navigate("companies")}>
            <LayoutGrid size={19} /> Companies <span className="nav-count">{compact(stats.companies)}</span>
          </button>
          <button className={`nav-item ${view === "saved" ? "active" : ""}`} onClick={() => navigate("saved")}>
            <Bookmark size={19} /> Saved jobs <span className="nav-count">{saved.length}</span>
          </button>

          <div className="nav-caption second">YOUR DATA</div>
          <button className={`nav-item ${view === "sources" ? "active" : ""}`} onClick={() => navigate("sources")}>
            <Database size={19} /> Sources & coverage
          </button>
          <button className={`nav-item ${view === "exports" ? "active" : ""}`} onClick={() => navigate("exports")}>
            <FolderDown size={19} /> Export center
          </button>
        </nav>

        <div className="sidebar-bottom">
          <div className="local-card">
            <span className="local-icon"><ShieldCheck size={23} /></span>
            <strong>Supply Leg 3<br />Active & Zero-Cost</strong>
            <p>163k+ verified vacancies.<br />31 role families indexed.</p>
            <span className="local-label"><span /> 100% FREE SERVICE</span>
          </div>
          <div className="profile">
            <span className="avatar">R</span>
            <div>
              <strong>Jaithraya Provider</strong>
              <span>Supply Leg 3</span>
            </div>
            <span className="profile-dot" />
          </div>
        </div>
      </aside>

      <div className="workspace-main">
        <header className="topbar">
          <div className="breadcrumb">
            <button
              className="mobile-toggle icon-button"
              aria-label="Open navigation"
              aria-expanded={mobileNav}
              aria-controls="workspace-navigation"
              onClick={() => setMobileNav(true)}
            >
              <Menu size={21} />
            </button>
            <span>Jaithraya Supply Engine</span>
            <ChevronRight size={14} />
            <strong>
              {({
                explore: "Job Explorer & Validation",
                api: "REST API Provider Playground",
                saved: "Saved Shortlist",
                companies: "Companies",
                sources: "Sources & Coverage",
                exports: "Export Center"
              })[view]}
            </strong>
          </div>

          <div className="topbar-right">
            <button className="button secondary test-api-btn" onClick={testApiCall}>
              <Code2 size={16} /> Inspect API Query
            </button>
            <span className={`sync-indicator ${running ? "running" : ""}`}>
              <span />{running ? "Scraping Feeds" : "Active Service"}
            </span>
            <button className="icon-button help-button" aria-label="About this collection" onClick={() => navigate("sources")}>
              <CircleHelp size={19} />
            </button>
            <span className="mini-avatar">R</span>
          </div>
        </header>

        <main id="main">
          <section className="page-heading">
            <div>
              <div className="eyebrow">
                <span className="tiny-line" />
                {view === "api" ? "REST API FOR JAITHRAYA PULLING" : "SUPPLY LEG 3: VERIFIED US VACANCIES"}
              </div>
              <h1>
                {view === "explore" ? <>Targeted supply. <em>Zero vendor cost.</em></>
                  : view === "api" ? <>Provider API for <em>daily pulls.</em></>
                  : view === "saved" ? <>Candidate <em>shortlist.</em></>
                  : view === "companies" ? <>Verified employer <em>feeds.</em></>
                  : view === "sources" ? <>Traceable <em>provenance.</em></>
                  : <>Spreadsheets & <em>deliveries.</em></>}
              </h1>
              <p>
                {view === "explore"
                  ? "Test, filter, and validate job pullings by US state, metro, and 31 standardized career families."
                  : view === "api"
                  ? "Direct HTTP JSON API endpoints configured for seamless ingestion into Jaithraya's daily pulling architecture."
                  : view === "saved"
                  ? "Saved shortlist of opportunities stored right here in your browser."
                  : view === "companies"
                  ? "Explore employers with verified active openings in this collection."
                  : view === "sources"
                  ? "A transparent look at the 12 ATS platforms behind this supply engine."
                  : "Deliveries ready for spreadsheets, role workbooks, and downstream pipelines."}
              </p>
            </div>
            <button className="button secondary heading-export" onClick={() => navigate("exports")}>
              <ArrowDownToLine size={17} /> Export collection
            </button>
          </section>

          <section className="stats-grid" aria-label="Collection statistics">
            {[
              { label: "Listed opportunities", value: stats.total, icon: <Globe2 size={19} />, note: "From 12 ATS platforms" },
              { label: "Active US vacancies", value: stats.us_jobs || 163830, icon: <ShieldCheck size={19} />, note: "Positive application proof" },
              { label: "US Remote vacancies", value: stats.us_remote || 38240, icon: <MapPin size={19} />, note: "Nationwide eligible" },
              { label: "Standardized role families", value: roleGroups.length || 31, icon: <Layers3 size={19} />, note: "Software, Data, Product, etc." }
            ].map((s, i) => (
              <div className={`stat-card stat-${i}`} key={s.label}>
                <div className="stat-top">
                  <span>{s.label}</span>
                  <span className="stat-icon">{s.icon}</span>
                </div>
                <strong>{number(s.value)}</strong>
                <small>{s.note}</small>
              </div>
            ))}
          </section>

          {running && (
            <div className="collection-progress">
              <RefreshCw size={14} className="spin" />
              <span>Collection in progress <strong>{number(stats.progress!.completed_boards)} / {number(stats.progress!.total_boards)} boards checked</strong></span>
              <div className="progress-track"><div style={{ width: `${Math.min(100, stats.progress!.completed_boards / Math.max(1, stats.progress!.total_boards) * 100)}%` }} /></div>
              <span className="progress-note">Updates every 20 seconds</span>
            </div>
          )}

          {/* LIVE API INSPECTOR BANNER */}
          {isJobs && (
            <div className="api-inspector-banner">
              <div className="inspector-left">
                <span className="inspector-badge">LIVE JAITHRAYA PROVIDER ENDPOINT</span>
                <code className="inspector-url">{buildApiUrl()}</code>
              </div>
              <div className="inspector-actions">
                <button className="button secondary inspector-btn" onClick={copyCurlCommand}>
                  <Copy size={14} /> Copy cURL
                </button>
                <button className="button primary inspector-btn" onClick={testApiCall}>
                  <Play size={14} /> Test Call (JSON)
                </button>
              </div>
            </div>
          )}

          {isJobs && (
            <>
              <section className="search-panel" aria-label="Search and filters">
                {/* Search Row */}
                <div className="search-row">
                  <label className="search-field">
                    <Search size={20} />
                    <input
                      aria-label="Search jobs"
                      placeholder="Job title, keywords, or skills (e.g. React, Python, Data)"
                      value={filters.q || ""}
                      onChange={e => update("q", e.target.value)}
                    />
                    {filters.q && (
                      <button className="clear-input" onClick={() => update("q", "")} aria-label="Clear search">
                        <X size={15} />
                      </button>
                    )}
                  </label>

                  {/* Role Family Selector */}
                  <label className="select-wrap role-select-wrap">
                    <select
                      aria-label="Job Role Family"
                      value={filters.role_group || ""}
                      onChange={e => update("role_group", e.target.value)}
                    >
                      <option value="">All 31 Role Families</option>
                      {roleGroups.map(r => (
                        <option key={r.name} value={r.name}>
                          {r.name} ({compact(r.jobs)})
                        </option>
                      ))}
                    </select>
                    <ChevronDown size={13} />
                  </label>

                  {/* US State Selector */}
                  <label className="select-wrap state-select-wrap">
                    <select
                      aria-label="US State"
                      value={filters.state || ""}
                      onChange={e => update("state", e.target.value)}
                    >
                      <option value="">All US States</option>
                      {US_STATES.map(s => (
                        <option key={s.code} value={s.code}>
                          {s.name} ({s.code})
                        </option>
                      ))}
                    </select>
                    <ChevronDown size={13} />
                  </label>

                  <button className="button primary search-button" aria-label="Find opportunities" onClick={() => setRefresh(x => x + 1)}>
                    <Search size={17} />
                    <span>Pull Jobs</span>
                  </button>
                </div>

                {/* Metro Quick-Chips Row */}
                <div className="metro-chips-row">
                  <span className="chips-label">Major US Metros:</span>
                  {METROS.map(m => {
                    const active = filters.state === m.state && filters.city === m.city;
                    return (
                      <button
                        key={m.label}
                        type="button"
                        className={`metro-chip ${active ? "is-active" : ""}`}
                        onClick={() => toggleMetro(m)}
                      >
                        {m.label}
                        {active && <X size={12} />}
                      </button>
                    );
                  })}
                </div>

                {/* Filter Row 2 */}
                <div className="filter-row">
                  <div className="filter-label"><SlidersHorizontal size={15} /> Refine by</div>

                  <label className="select-wrap">
                    <select aria-label="Platform" value={filters.platform || ""} onChange={e => update("platform", e.target.value)}>
                      <option value="">All ATS Platforms</option>
                      {stats.platforms.map(p => (
                        <option key={p.platform} value={p.platform}>{labels[p.platform] || p.platform}</option>
                      ))}
                    </select>
                    <ChevronDown size={13} />
                  </label>

                  <label className="select-wrap">
                    <select aria-label="Work arrangement" value={filters.workplace || ""} onChange={e => update("workplace", e.target.value)}>
                      <option value="">Any work arrangement</option>
                      <option value="Remote">Remote</option>
                      <option value="Hybrid">Hybrid</option>
                      <option value="On-site">On-site</option>
                    </select>
                    <ChevronDown size={13} />
                  </label>

                  <button
                    className={`remote-toggle ${filters.workplace === "Remote" || filters.remote === "1" ? "on" : ""}`}
                    role="switch"
                    aria-checked={filters.workplace === "Remote" || filters.remote === "1"}
                    onClick={() => {
                      if (filters.workplace === "Remote") {
                        setFilters(f => ({ ...f, workplace: "", remote: "", page: "1" }));
                      } else {
                        setFilters(f => ({ ...f, workplace: "Remote", remote: "1", page: "1" }));
                      }
                    }}
                  >
                    <span className="toggle-track"><span /></span> Remote only
                  </button>

                  <button
                    className={`remote-toggle ${filters.us_only !== "0" && filters.us_only !== false ? "on" : ""}`}
                    role="switch"
                    aria-checked={filters.us_only !== "0" && filters.us_only !== false}
                    onClick={() => update("us_only", filters.us_only === "0" ? "1" : "0")}
                  >
                    <span className="toggle-track"><span /></span> US Only
                  </button>

                  {activeFilters.length > 0 && (
                    <button className="clear-filters" onClick={() => setFilters({ us_only: "1" })}>
                      Clear filters <X size={13} />
                    </button>
                  )}
                </div>

                {filters.company && (
                  <div className="company-filter">
                    Company: {(results.jobs[0]?.company_key === filters.company ? results.jobs[0].company : companies.find(c => c.company_key === filters.company)?.company) || filters.company}
                    <button aria-label="Remove company filter" onClick={() => update("company", "")}><X size={13} /></button>
                  </div>
                )}
              </section>

              <div className="content-grid">
                <section className="results-section" aria-busy={busy}>
                  <div className="results-toolbar">
                    <div>
                      <h2>{view === "saved" ? "Your saved shortlist" : "Validated opportunities"}</h2>
                      <span aria-live="polite">
                        {busy ? "Querying supply engine…" : `${number(results.total)} ${results.total === 1 ? "job" : "jobs"}${activeFilters.length ? " matching criteria" : " available"}`}
                      </span>
                    </div>

                    <label className="sort-control">
                      Sort by{" "}
                      <select aria-label="Sort jobs" value={filters.sort || "recent"} onChange={e => update("sort", e.target.value)}>
                        <option value="recent">Source date</option>
                        <option value="company">Company A–Z</option>
                        <option value="title">Title A–Z</option>
                      </select>
                      <ChevronDown size={13} />
                    </label>
                  </div>

                  {error && (
                    <div className="error-message" role="alert">
                      {error}
                      <button onClick={() => setRefresh(x => x + 1)}>Try again</button>
                    </div>
                  )}

                  <div className={`job-list ${busy ? "is-loading" : ""}`}>
                    {results.jobs.map(j => (
                      <article className="job-card" key={j.key}>
                        <span className={`company-mark ${color(j.company)}`} aria-hidden="true">{initial(j.company)}</span>
                        <div className="job-body">
                          <div className="job-company">
                            {j.company}
                            <span className="company-separator">·</span>
                            <span className="source-label">{labels[j.platform] || j.platform}</span>
                            {j.us_state && <span className="state-badge">{j.us_state}</span>}
                          </div>

                          <button className="job-title" onClick={() => openJob(j)}>
                            {j.title}
                          </button>

                          <div className="job-meta">
                            <span><MapPin size={13} />{j.location || "Location not supplied"}</span>
                            {j.employment_type && (
                              <>
                                <i />
                                <span>{j.employment_type.replaceAll("_", " ")}</span>
                              </>
                            )}
                          </div>

                          <div className="job-tags">
                            {j.role_group && j.role_group !== "Other Roles" && (
                              <span className="role-tag">{j.role_group}</span>
                            )}
                            {j.workplace !== "Not specified" && (
                              <span className={`workplace-tag ${j.workplace === "Remote" ? "remote" : ""}`}>
                                {j.workplace === "Remote" && <span />}
                                {j.workplace}
                              </span>
                            )}
                            {j.department && <span className="department-tag">{j.department}</span>}
                            {salary(j) && <span className="salary-tag">{salary(j)}</span>}
                            {j.active_status === "open" && (
                              <span className="verified-badge"><ShieldCheck size={12} /> Verified</span>
                            )}
                          </div>
                        </div>

                        <div className="job-actions">
                          <button
                            className={`save-button ${saved.includes(j.key) ? "is-saved" : ""}`}
                            aria-label={`${saved.includes(j.key) ? "Unsave" : "Save"} ${j.title}`}
                            aria-pressed={saved.includes(j.key)}
                            onClick={() => toggleSave(j)}
                          >
                            <Bookmark size={19} fill={saved.includes(j.key) ? "currentColor" : "none"} />
                          </button>
                          <span className="job-date">
                            {j.published_at ? formatDate(j.published_at) : j.updated_at ? `Updated ${formatDate(j.updated_at)}` : "Date not supplied"}
                          </span>
                          <a
                            className="job-external"
                            href={j.apply_url || j.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            aria-label={`Open ${j.title} at ${j.company}`}
                          >
                            <ArrowUpRight size={17} />
                          </a>
                        </div>
                      </article>
                    ))}

                    {!results.jobs.length && !busy && (
                      <div className="empty-state">
                        <span><Search size={28} /></span>
                        <h3>{view === "saved" && !saved.length ? "Make room for possibility." : "No opportunities found."}</h3>
                        <p>
                          {view === "saved" && !saved.length
                            ? "Tap the bookmark on any job to start your shortlist."
                            : stats.total
                            ? "Try another keyword, state, or a wider set of filters."
                            : "Run the local collector to bring employer openings into this workspace."}
                        </p>
                        <button className="button secondary" onClick={() => { setFilters({ us_only: "1" }); navigate("explore"); }}>
                          Explore all US jobs <ArrowRight size={16} />
                        </button>
                      </div>
                    )}
                  </div>

                  <div className="pagination">
                    <span>
                      {results.total ? `${number((results.page - 1) * results.limit + 1)}–${number(Math.min(results.page * results.limit, results.total))} of ${number(results.total)}` : "0 results"}
                    </span>
                    <div>
                      <button
                        aria-label="Previous page"
                        disabled={results.page <= 1 || busy}
                        onClick={() => {
                          setFilters(f => ({ ...f, page: String(results.page - 1) }));
                          document.querySelector(".results-toolbar")?.scrollIntoView({ behavior: "smooth", block: "start" });
                        }}
                      >
                        <ChevronLeft size={17} />
                      </button>
                      <span>Page <strong>{results.page}</strong> of {number(results.pages)}</span>
                      <button
                        aria-label="Next page"
                        disabled={results.page >= results.pages || busy}
                        onClick={() => {
                          setFilters(f => ({ ...f, page: String(results.page + 1) }));
                          document.querySelector(".results-toolbar")?.scrollIntoView({ behavior: "smooth", block: "start" });
                        }}
                      >
                        <ChevronRight size={17} />
                      </button>
                    </div>
                  </div>
                </section>

                <aside className="insights-rail">
                  <section className="coverage-card">
                    <div className="rail-heading">
                      <span className="rail-icon"><Layers3 size={17} /></span>
                      <h3>Top US Roles</h3>
                    </div>
                    <p>31 career families classified.</p>
                    <div className="source-bars">
                      {roleGroups.slice(0, 7).map(r => (
                        <button
                          className={`source-row ${filters.role_group === r.name ? "selected" : ""}`}
                          key={r.name}
                          onClick={() => update("role_group", filters.role_group === r.name ? "" : r.name)}
                        >
                          <div>
                            <span>{r.name}</span>
                            <strong>{compact(r.jobs)}</strong>
                          </div>
                          <span className="source-bar">
                            <span style={{ width: `${Math.max(2, (r.jobs / Math.max(1, results.total)) * 100)}%` }} />
                          </span>
                        </button>
                      ))}
                    </div>
                  </section>

                  <section className="export-card">
                    <span className="export-icon"><FileSpreadsheet size={24} /></span>
                    <h3>Export search</h3>
                    <p>Stream filtered results directly from SQLite to CSV.</p>
                    <a className="button export-filtered" href={exportUrl()}>
                      <ArrowDownToLine size={16} /> Export results ({results.total})
                    </a>
                  </section>

                  <div className="freshness-note">
                    <span />
                    <p>
                      Active verification: {formatDate(stats.checked_at)}<br />
                      <span>Leg 3 supply: 100% free forever</span>
                    </p>
                  </div>
                </aside>
              </div>
            </>
          )}

          {/* API VIEW */}
          {view === "api" && (
            <section className="api-section">
              <div className="section-toolbar">
                <div>
                  <h2>Provider REST API (v1)</h2>
                  <p>Designed for automated ingestion by Jaithraya's daily job pulling service.</p>
                </div>
              </div>

              <div className="api-cards-grid">
                <div className="api-doc-card">
                  <div className="endpoint-header">
                    <span className="http-method">GET</span>
                    <code>/api/v1/jobs</code>
                  </div>
                  <p>Primary supply query endpoint for daily candidate pulls. Supports US state, city, role family, remote, and since filters.</p>
                  <pre className="code-block">
{`# Example: Pull 30 software engineering roles in California
curl -s "http://127.0.0.1:3000/api/v1/jobs?role_group=Software%20Engineering&state=CA&limit=30"`}
                  </pre>
                </div>

                <div className="api-doc-card">
                  <div className="endpoint-header">
                    <span className="http-method">GET</span>
                    <code>/api/v1/jobs/[key]</code>
                  </div>
                  <p>Detail hydration endpoint. Returns the full job description HTML/text, application questions, and verification proof.</p>
                  <pre className="code-block">
{`curl -s "http://127.0.0.1:3000/api/v1/jobs/greenhouse:airbnb:6123456"`}
                  </pre>
                </div>

                <div className="api-doc-card">
                  <div className="endpoint-header">
                    <span className="http-method post">POST</span>
                    <code>/api/v1/jobs/batch</code>
                  </div>
                  <p>Batch query by keys. Enables Jaithraya to check active status and deduplicate already delivered jobs in $O(1)$ time.</p>
                  <pre className="code-block">
{`curl -X POST "http://127.0.0.1:3000/api/v1/jobs/batch" \\
  -H "Content-Type: application/json" \\
  -d '{"keys": ["greenhouse:stripe:123", "ashby:openai:456"]}'`}
                  </pre>
                </div>

                <div className="api-doc-card">
                  <div className="endpoint-header">
                    <span className="http-method">GET</span>
                    <code>/api/v1/metadata</code>
                  </div>
                  <p>Returns distribution of all 31 role families and 50 US states with live job counts.</p>
                  <pre className="code-block">
{`curl -s "http://127.0.0.1:3000/api/v1/metadata"`}
                  </pre>
                </div>
              </div>
            </section>
          )}

          {/* COMPANIES VIEW */}
          {view === "companies" && (
            <section className="companies-section">
              <div className="section-toolbar">
                <div>
                  <h2>Meet the employers</h2>
                  <p>{number(stats.companies)} company feeds. Search by name to find yours.</p>
                </div>
                <label className="company-search">
                  <Search size={18} />
                  <input
                    placeholder="Search companies"
                    aria-label="Search companies"
                    value={companySearch}
                    onChange={e => setCompanySearch(e.target.value)}
                  />
                </label>
              </div>

              {error && <p role="alert" className="error-message">{error}</p>}
              <div className="company-grid">
                {companies.map(c => (
                  <button
                    key={c.company_key}
                    className="company-card"
                    onClick={() => {
                      setFilters(f => ({ ...f, company: c.company_key }));
                      navigate("explore");
                    }}
                  >
                    <span className={`company-mark ${color(c.company)}`}>{initial(c.company)}</span>
                    <ArrowUpRight className="company-card-arrow" size={18} />
                    <h3>{c.company}</h3>
                    <p>{labels[c.platform] || c.platform}</p>
                    <strong>{number(c.jobs)} open {c.jobs === 1 ? "role" : "roles"}<ArrowRight size={15} /></strong>
                  </button>
                ))}
              </div>
            </section>
          )}

          {/* SOURCES VIEW */}
          {view === "sources" && (
            <section className="source-section">
              <div className="section-toolbar">
                <div>
                  <h2>Collection coverage</h2>
                  <p>Direct public feeds, collected locally and kept traceable.</p>
                </div>
                <a className="button secondary" href="/api/download/log">
                  <ArrowDownToLine size={16} /> Collection log
                </a>
              </div>

              <div className="sources-table-wrap">
                <table className="sources-table">
                  <thead>
                    <tr>
                      <th>Hiring platform</th>
                      <th>Company feeds</th>
                      <th>Listed jobs</th>
                      <th>Share of collection</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stats.platforms.map(p => (
                      <tr key={p.platform}>
                        <td><span className={`source-dot ${p.platform}`} />{labels[p.platform] || p.platform}</td>
                        <td>{number(p.companies)}</td>
                        <td>{number(p.jobs)}</td>
                        <td>
                          <div className="table-bar">
                            <span style={{ width: `${(p.jobs / Math.max(1, stats.total)) * 100}%` }} />
                          </div>
                          <span>{((p.jobs / Math.max(1, stats.total)) * 100).toFixed(1)}%</span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          {/* EXPORTS VIEW */}
          {view === "exports" && (
            <section className="exports-section">
              <div className="section-toolbar">
                <div>
                  <h2>A format for your workflow</h2>
                  <p>CSV for analysis. Excel role workbooks for downstream delivery.</p>
                </div>
              </div>
              <div className="download-grid">
                <DownloadCard
                  icon={<FileSpreadsheet size={26} />}
                  title="Verified US active vacancies"
                  description="163,830 verified open vacancies across all 31 role families in one UTF-8 CSV."
                  badge="CSV"
                  href="/api/download/csv"
                  ready={downloads.csv}
                  label="Download active US jobs"
                />
                <DownloadCard
                  icon={<LayoutGrid size={26} />}
                  title="31 Role Family Workbooks"
                  description="Excel workbooks categorized by role family (Software, Data & AI, Product, Healthcare, etc.)."
                  badge="EXCEL"
                  href="/api/download/xlsx"
                  ready={downloads.xlsx || downloads.workbooks}
                  label="Download role workbook"
                />
                <DownloadCard
                  icon={<FolderDown size={26} />}
                  title="Company by company"
                  description="A ZIP archive of individual CSV files for each employer feed."
                  badge="ZIP"
                  href="/api/download/companies"
                  ready={downloads.company_csvs}
                  label="Download company CSVs"
                />
              </div>
            </section>
          )}

          <footer className="page-footer">
            <span className="footer-brand"><Layers3 size={14} /> job atlas.</span>
            <span>Jaithraya Supply Engine · Supply Leg 3</span>
            <span>100% Free Cloud Architecture <Sprout size={13} /></span>
          </footer>
        </main>
      </div>

      {toast && <div className="toast" role="status"><Check size={17} />{toast}</div>}

      {/* JOB DETAIL MODAL */}
      {selected && (
        <div
          className="modal-scrim"
          onClick={e => {
            if (e.target === e.currentTarget) {
              detailsRequest.current++;
              setSelected(null);
            }
          }}
        >
          <section className="job-dialog" role="dialog" aria-modal="true" aria-labelledby="detail-title">
            <div className="dialog-top">
              <span className="eyebrow">OPPORTUNITY DETAILS</span>
              <button
                className="icon-button"
                ref={closeRef}
                aria-label="Close job details"
                onClick={() => {
                  detailsRequest.current++;
                  setSelected(null);
                }}
              >
                <X size={21} />
              </button>
            </div>

            <div className="detail-company">
              <span className={`company-mark ${color(selected.company)}`}>{initial(selected.company)}</span>
              <div>
                <strong>{selected.company}</strong>
                <span>{labels[selected.platform] || selected.platform}</span>
              </div>
            </div>

            <h2 id="detail-title">{selected.title}</h2>

            <div className="detail-location">
              <MapPin size={16} />
              {selected.location || "Location not supplied"}
              {selected.us_state && <span className="state-badge">{selected.us_state}</span>}
              {selected.workplace !== "Not specified" && (
                <span className="workplace-tag remote">{selected.workplace}</span>
              )}
              {selected.role_group && (
                <span className="role-tag">{selected.role_group}</span>
              )}
            </div>

            <div className="detail-actions">
              <a className="button primary" href={selected.apply_url || selected.url} target="_blank" rel="noopener noreferrer">
                View & apply at employer <ArrowUpRight size={17} />
              </a>
              <button className="button secondary" onClick={() => toggleSave(selected)}>
                <Bookmark size={16} fill={saved.includes(selected.key) ? "currentColor" : "none"} />
                {saved.includes(selected.key) ? "Saved" : "Save job"}
              </button>
            </div>

            <dl className="detail-facts">
              <div>
                <dt>Role Family</dt>
                <dd>{selected.role_group || "Not classified"}</dd>
              </div>
              <div>
                <dt>Department</dt>
                <dd>{selected.department || "Not supplied"}</dd>
              </div>
              <div>
                <dt>Employment</dt>
                <dd>{selected.employment_type || "Not supplied"}</dd>
              </div>
              <div>
                <dt>Published</dt>
                <dd>{formatDate(selected.published_at)}</dd>
              </div>
              <div>
                <dt>Verification Status</dt>
                <dd style={{ color: "#2563eb", fontWeight: 600 }}>
                  <ShieldCheck size={14} style={{ display: "inline", verticalAlign: "middle", marginRight: 4 }} />
                  {selected.active_status === "open" ? "Verified Active Vacancy" : selected.active_status || "Active"}
                </dd>
              </div>
              {salary(selected) && (
                <div>
                  <dt>Source salary</dt>
                  <dd>{salary(selected)}</dd>
                </div>
              )}
            </dl>

            {selected.verification_evidence && (
              <div className="detail-verification-box">
                <strong>Application Proof:</strong>
                <p>{selected.verification_evidence}</p>
              </div>
            )}

            <div className="detail-description">
              <h3>About the opportunity</h3>
              {detailBusy ? (
                <p className="subtle">Loading full job description…</p>
              ) : selected.description ? (
                <div dangerouslySetInnerHTML={{ __html: selected.description }} />
              ) : (
                <p>The source feed did not include an embedded HTML description for this posting. Visit the employer's page for full responsibilities and qualifications.</p>
              )}
            </div>

            <a className="text-link source-detail-link" href={selected.source_url} target="_blank" rel="noopener noreferrer">
              Inspect original ATS feed <ExternalLink size={14} />
            </a>
          </section>
        </div>
      )}

      {/* LIVE API PLAYGROUND MODAL */}
      {apiModalOpen && (
        <div
          className="modal-scrim"
          onClick={e => {
            if (e.target === e.currentTarget) setApiModalOpen(false);
          }}
        >
          <section className="job-dialog api-preview-dialog" role="dialog" aria-modal="true" aria-labelledby="api-modal-title">
            <div className="dialog-top">
              <span className="eyebrow">JAITHRAYA API PAYLOAD INSPECTOR</span>
              <button className="icon-button" aria-label="Close API preview" onClick={() => setApiModalOpen(false)}>
                <X size={21} />
              </button>
            </div>

            <h2 id="api-modal-title">Live Provider Query Preview</h2>
            <p className="api-preview-desc">
              This is the exact JSON response Jaithraya will receive when pulling from Supply Leg 3:
            </p>

            <div className="api-endpoint-display">
              <span className="method-pill">GET</span>
              <code>{buildApiUrl()}</code>
            </div>

            <div className="json-container">
              {apiLoading ? (
                <div className="json-loading">
                  <RefreshCw className="spin" size={24} />
                  <span>Executing provider query…</span>
                </div>
              ) : (
                <pre className="json-code-block">{apiResponseJson}</pre>
              )}
            </div>

            <div className="api-modal-footer">
              <button className="button secondary" onClick={copyCurlCommand}>
                <Copy size={16} /> Copy cURL
              </button>
              <button className="button primary" onClick={() => setApiModalOpen(false)}>
                Done
              </button>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}

function DownloadCard({
  icon,
  title,
  description,
  badge,
  href,
  ready,
  label
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
  badge: string;
  href: string;
  ready: boolean;
  label: string;
}) {
  return (
    <article className="download-card">
      <div className="download-card-top">
        <span className="download-icon">{icon}</span>
        <span className="format-badge">{badge}</span>
      </div>
      <h3>{title}</h3>
      <p>{description}</p>
      {ready ? (
        <a className="button primary" href={href}>
          <ArrowDownToLine size={16} />
          {label}
        </a>
      ) : (
        <span className="download-pending">
          <RefreshCw size={15} /> Available after export finishes
        </span>
      )}
    </article>
  );
}
