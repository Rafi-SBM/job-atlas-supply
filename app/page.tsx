import Dashboard from "@/components/dashboard";
import { getJobs, getStats, getCompanies, getDownloads, getMetadata } from "@/lib/data";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export default function Page() {
  return (
    <Dashboard
      initialResults={getJobs({ us_only: "1" })}
      initialStats={getStats()}
      initialCompanies={getCompanies()}
      initialMetadata={getMetadata()}
      downloads={getDownloads()}
    />
  );
}
