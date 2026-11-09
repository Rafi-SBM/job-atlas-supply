import { NextResponse } from "next/server";
import fs from "node:fs";
import path from "node:path";
import { Readable } from "node:stream";
export const runtime = "nodejs";
export const dynamic = "force-dynamic";
const files: Record<string, string> = { csv: "all_jobs.csv", companies: "company_csvs.zip", xlsx: "jobs_by_company.xlsx", workbooks: "company_workbooks.zip", log: "collection_log.csv", manifest: "manifest.json" };
export async function GET(_request: Request, { params }: { params: Promise<{file: string}> }) {
  const { file } = await params;
  const name = files[file];
  if (!name) return NextResponse.json({error: "Unknown download"}, {status: 404});
  const full = path.join(process.cwd(), "outputs", "job-atlas", name);
  if (!fs.existsSync(full)) return NextResponse.json({error: "This export has not been generated yet."}, {status: 404});
  const contentType = name.endsWith(".csv") ? "text/csv; charset=utf-8" : name.endsWith(".xlsx") ? "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" : name.endsWith(".json") ? "application/json" : "application/zip";
  return new Response(Readable.toWeb(fs.createReadStream(full)) as ReadableStream, {headers: { "Content-Type": contentType, "Content-Length": String(fs.statSync(full).size), "Content-Disposition": `attachment; filename="${name}"`, "Cache-Control": "no-store" }});
}
