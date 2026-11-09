import { NextRequest, NextResponse } from "next/server";
import { getCompanies, db } from "@/lib/data";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const q = request.nextUrl.searchParams.get("q") || "";
  if (!db()) {
    const backend = process.env.ATLAS_BACKEND_URL || "https://job-atlas-supply.onrender.com";
    try {
      const res = await fetch(`${backend}/api/companies?q=${encodeURIComponent(q)}`, { cache: "no-store" });
      if (res.ok) {
        return NextResponse.json(await res.json());
      }
    } catch {}
  }
  return NextResponse.json(getCompanies(q));
}

