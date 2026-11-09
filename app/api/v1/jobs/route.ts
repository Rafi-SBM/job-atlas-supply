import { NextRequest, NextResponse } from "next/server";
import { getJobs, type Filters } from "@/lib/data";

export const dynamic = "force-dynamic";

export function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const filters: Filters = {};

  const paramKeys = [
    "q", "title", "location", "platform", "company", "workplace",
    "sort", "page", "role_group", "state", "us_state", "city",
    "us_city", "remote", "us_only", "active_only", "since",
    "limit", "exclude_keys"
  ] as const;

  for (const key of paramKeys) {
    const val = searchParams.get(key);
    if (val !== null && val !== "") {
      filters[key] = val;
    }
  }

  // Default to US-only if not explicitly specified
  if (filters.us_only === undefined) {
    filters.us_only = "1";
  }

  // Default limit to 30 (matching Jaithraya's daily delivery floor)
  if (!filters.limit) {
    filters.limit = 30;
  }

  const result = getJobs(filters);

  const formattedData = result.jobs.map(j => ({
    id: j.key,
    key: j.key,
    title: j.title,
    company: j.company,
    company_key: j.company_key,
    platform: j.platform,
    board: j.board,
    job_id: j.job_id,
    location: j.location,
    is_us: Boolean(j.is_us),
    us_state: j.us_state || null,
    us_city: j.us_city || null,
    workplace: j.workplace,
    role_group: j.role_group || "Other Roles",
    department: j.department || null,
    employment_type: j.employment_type || null,
    salary_min: j.salary_min,
    salary_max: j.salary_max,
    salary_currency: j.salary_currency || null,
    salary_interval: j.salary_interval || null,
    salary_text: j.salary_text || null,
    url: j.url,
    apply_url: j.apply_url || j.url,
    source_url: j.source_url,
    published_at: j.published_at || null,
    updated_at: j.updated_at || null,
    checked_at: j.checked_at,
    active: true,
    verification: {
      status: j.active_status || "open",
      evidence: j.verification_evidence || null,
      verified_at: j.verified_at || null,
    }
  }));

  return NextResponse.json({
    status: "success",
    total: result.total,
    page: result.page,
    pages: result.pages,
    limit: result.limit,
    has_more: result.page < result.pages,
    data: formattedData
  });
}
