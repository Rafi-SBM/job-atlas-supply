import { NextRequest, NextResponse } from "next/server";
import { getJobsBatch, db } from "@/lib/data";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const keys = Array.isArray(body?.keys) ? body.keys.filter((k: unknown) => typeof k === "string") : [];

    if (!db()) {
      const backend = process.env.ATLAS_BACKEND_URL || "https://job-atlas-supply.onrender.com";
      try {
        const res = await fetch(`${backend}/api/v1/jobs/batch`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ keys }),
          cache: "no-store",
        });
        if (res.ok) {
          return NextResponse.json(await res.json());
        }
      } catch {}
    }

    if (!keys.length) {
      return NextResponse.json({
        status: "success",
        total: 0,
        data: []
      });
    }

    const jobs = getJobsBatch(keys);
    const formattedData = jobs.map(j => ({
      id: j.key,
      key: j.key,
      title: j.title,
      company: j.company,
      company_key: j.company_key,
      platform: j.platform,
      board: j.board,
      location: j.location,
      is_us: Boolean(j.is_us),
      us_state: j.us_state || null,
      us_city: j.us_city || null,
      workplace: j.workplace,
      role_group: j.role_group || "Other Roles",
      salary_min: j.salary_min,
      salary_max: j.salary_max,
      salary_text: j.salary_text || null,
      url: j.url,
      apply_url: j.apply_url || j.url,
      active: true,
      verification_status: j.active_status || "open"
    }));

    return NextResponse.json({
      status: "success",
      total: formattedData.length,
      data: formattedData
    });
  } catch (err) {
    return NextResponse.json(
      { status: "error", message: err instanceof Error ? err.message : "Invalid JSON payload" },
      { status: 400 }
    );
  }
}

