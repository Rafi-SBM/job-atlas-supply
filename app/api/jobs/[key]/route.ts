import { NextResponse } from "next/server";
import { getJob, db } from "@/lib/data";

export const dynamic = "force-dynamic";

export async function GET(_request: Request, { params }: { params: Promise<{key: string}> }) {
  const { key } = await params;
  if (!db()) {
    const backend = process.env.ATLAS_BACKEND_URL || "https://job-atlas-supply.onrender.com";
    try {
      const res = await fetch(`${backend}/api/jobs/${encodeURIComponent(key)}`, { cache: "no-store" });
      if (res.ok) {
        return NextResponse.json(await res.json());
      }
    } catch {}
  }
  const job = getJob(key);
  return job ? NextResponse.json(job) : NextResponse.json({ error: "This job is no longer in the active local collection." }, { status: 404 });
}
