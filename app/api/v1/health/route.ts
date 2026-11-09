import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export function GET() {
  return NextResponse.json({
    status: "ok",
    service: "job-atlas-supply-engine",
    version: "1.0.0",
    leg: "Supply Leg 3 (Job Atlas)",
    uptime_seconds: Math.floor(process.uptime()),
    timestamp: new Date().toISOString()
  });
}

