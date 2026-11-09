import Dashboard from "@/components/dashboard";
import { getJobs, getStats, getCompanies, getDownloads, getMetadata } from "@/lib/data";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export default async function Page() {
  const backend = process.env.ATLAS_BACKEND_URL || "https://job-atlas-supply.onrender.com";
  let initialResults = getJobs({ us_only: "1" });
  let initialCompanies = getCompanies();

  // If running in a serverless environment without local SQLite (e.g. Vercel), hydrate from Render backend
  if (initialResults.jobs.length === 0) {
    try {
      const res = await fetch(`${backend}/api/jobs?us_only=1&limit=25`, { next: { revalidate: 60 } });
      if (res.ok) {
        initialResults = await res.json();
      }
    } catch {}
  }

  if (initialCompanies.length === 0) {
    try {
      const res = await fetch(`${backend}/api/companies?limit=100`, { next: { revalidate: 300 } });
      if (res.ok) {
        initialCompanies = await res.json();
      }
    } catch {}
  }

  return (
    <Dashboard
      initialResults={initialResults}
      initialStats={getStats()}
      initialCompanies={initialCompanies}
      initialMetadata={getMetadata()}
      downloads={getDownloads()}
    />
  );
}
