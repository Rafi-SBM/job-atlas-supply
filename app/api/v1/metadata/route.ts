import { NextResponse } from "next/server";
import { getMetadata } from "@/lib/data";

export const dynamic = "force-dynamic";

export function GET() {
  const meta = getMetadata();
  return NextResponse.json({
    status: "success",
    total_jobs: meta.total_jobs,
    total_us_jobs: meta.total_us_jobs,
    total_us_remote: meta.total_us_remote,
    checked_at: meta.checked_at,
    role_groups: meta.role_groups,
    states: meta.states,
    platforms: meta.platforms
  });
}
