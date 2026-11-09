import { NextRequest, NextResponse } from "next/server";
import { getJobs, db } from "@/lib/data";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  if (!db()) {
    const backend = process.env.ATLAS_BACKEND_URL || "https://job-atlas-supply.onrender.com";
    try {
      const res = await fetch(`${backend}/api/jobs?${searchParams.toString()}`, { cache: "no-store" });
      if (res.ok) {
        return NextResponse.json(await res.json());
      }
    } catch {}
  }
  const filters: Record<string, string> = {};
  searchParams.forEach((val, key) => {
    if (val !== "") filters[key] = val;
  });
  return NextResponse.json(getJobs(filters));
}
