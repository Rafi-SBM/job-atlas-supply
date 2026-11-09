import { NextResponse } from "next/server";
import { getJob } from "@/lib/data";

export const dynamic = "force-dynamic";

export async function GET(_request: Request, { params }: { params: Promise<{key: string}> }) {
  const { key } = await params;
  const job = getJob(key);
  return job ? NextResponse.json(job) : NextResponse.json({ error: "This job is no longer in the active local collection." }, { status: 404 });
}
