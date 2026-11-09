import { NextRequest, NextResponse } from "next/server";
import { getJobs } from "@/lib/data";

export const dynamic = "force-dynamic";

export function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const filters: Record<string, string> = {};
  searchParams.forEach((val, key) => {
    if (val !== "") filters[key] = val;
  });
  return NextResponse.json(getJobs(filters));
}
