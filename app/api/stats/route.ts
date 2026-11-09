import { NextResponse } from "next/server";
import { getStats, getDownloads } from "@/lib/data";
export const dynamic = "force-dynamic";
export function GET() { return NextResponse.json({ ...getStats(), downloads: getDownloads() }); }
