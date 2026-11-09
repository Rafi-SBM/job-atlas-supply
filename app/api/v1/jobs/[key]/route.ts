import { NextRequest, NextResponse } from "next/server";
import { getJob } from "@/lib/data";

export const dynamic = "force-dynamic";

export async function GET(_request: NextRequest, { params }: { params: Promise<{ key: string }> }) {
  const { key } = await params;
  const decodedKey = decodeURIComponent(key);
  const job = getJob(decodedKey);

  if (!job) {
    return NextResponse.json(
      { status: "error", message: `Job with key '${decodedKey}' not found or no longer active.` },
      { status: 404 }
    );
  }

  return NextResponse.json({
    status: "success",
    data: {
      id: job.key,
      key: job.key,
      title: job.title,
      company: job.company,
      company_key: job.company_key,
      platform: job.platform,
      board: job.board,
      job_id: job.job_id,
      location: job.location,
      is_us: Boolean(job.is_us),
      us_state: job.us_state || null,
      us_city: job.us_city || null,
      workplace: job.workplace,
      role_group: job.role_group || "Other Roles",
      department: job.department || null,
      employment_type: job.employment_type || null,
      salary_min: job.salary_min,
      salary_max: job.salary_max,
      salary_currency: job.salary_currency || null,
      salary_interval: job.salary_interval || null,
      salary_text: job.salary_text || null,
      url: job.url,
      apply_url: job.apply_url || job.url,
      source_url: job.source_url,
      description: job.description || null,
      published_at: job.published_at || null,
      updated_at: job.updated_at || null,
      checked_at: job.checked_at,
      date_note: job.date_note || null,
      active: true,
      verification: {
        status: job.active_status || "open",
        evidence: job.verification_evidence || null,
        verified_at: job.verified_at || null,
      }
    }
  });
}
