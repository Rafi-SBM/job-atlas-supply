import { NextRequest } from "next/server";
import { exportRows } from "@/lib/data";
export const dynamic = "force-dynamic";
export const runtime = "nodejs";
function cell(v: unknown) {
  let s = String(v ?? "");
  if (/^[\s]*[=+@-]/.test(s)) s = "'" + s;
  return `"${s.replaceAll('"', '""')}"`;
}
export function GET(request: NextRequest) {
  const rows = exportRows(Object.fromEntries(request.nextUrl.searchParams));
  const fields = ["company","title","location","workplace","department","employment_type","platform","published_at","updated_at","salary_min","salary_max","salary_currency","salary_interval","salary_text","url","apply_url","source_url","checked_at","date_note","company_key","key"];
  const encoder = new TextEncoder();
  const iterator = rows?.[Symbol.iterator]();
  let started = false;
  const stream = new ReadableStream({
    pull(controller) {
      if (!started) { controller.enqueue(encoder.encode("\ufeff" + fields.join(",") + "\r\n")); started = true; }
      let chunk = "";
      for (let i = 0; i < 250; i++) {
        const next = iterator?.next();
        if (!next || next.done) { if (chunk) controller.enqueue(encoder.encode(chunk)); controller.close(); return; }
        chunk += fields.map(f => cell(next.value[f])).join(",") + "\r\n";
      }
      controller.enqueue(encoder.encode(chunk));
    },
    cancel() { iterator?.return?.(); },
  });
  return new Response(stream, { headers: { "Content-Type": "text/csv; charset=utf-8", "Content-Disposition": 'attachment; filename="job-atlas-filtered.csv"', "Cache-Control": "no-store" } });
}
