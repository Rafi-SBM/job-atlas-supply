import { NextRequest, NextResponse } from "next/server";
import { getCompanies } from "@/lib/data";

export const dynamic = "force-dynamic";

export function GET(request: NextRequest) {
  const q = request.nextUrl.searchParams.get("q") || "";
  return NextResponse.json(getCompanies(q));
}

