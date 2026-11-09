import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";

export const dynamic = "force-dynamic";

export interface CandidateSimulationSummary {
  handle: string;
  name: string;
  supply_enabled: boolean;
  daily_target: number;
  role_family: string;
  atlas_role_group: string;
  remote_preference: string;
  target_states: string[];
  cooldown_companies_history: number;
  raw_atlas_matching_jobs: number;
  cooldown_dropped_jobs: number;
  eligible_unique_companies: number;
  can_fulfill_daily_quota: boolean;
  days_of_supply_runway: number;
  target_titles: string[];
  locations: string[];
  all_excluded_companies: string[];
}

export function GET() {
  try {
    const trackedPath = path.join(process.cwd(), "lib", "candidates_data.json");
    if (fs.existsSync(trackedPath)) {
      const data = JSON.parse(fs.readFileSync(trackedPath, "utf8"));
      return NextResponse.json({
        status: "success",
        total_candidates: data.total_candidates,
        quota_pass_rate_pct: data.quota_pass_rate_pct,
        average_runway_days: data.average_runway_days,
        tested_at: data.tested_at,
        data: data.candidates
      });
    }

    const simPath = path.join(process.cwd(), "data", "atlas_candidate_simulation_results.json");
    const usersPath = path.join(process.cwd(), "data", "jaithraya_users.json");

    if (fs.existsSync(simPath) && fs.existsSync(usersPath)) {
      const simData = JSON.parse(fs.readFileSync(simPath, "utf8"));
      const usersData = JSON.parse(fs.readFileSync(usersPath, "utf8"));

      const userMap = new Map();
      for (const u of usersData.candidates || []) {
        userMap.set(u.handle, u);
      }

      const candidates: CandidateSimulationSummary[] = (simData.candidate_results || []).map((res: any) => {
        const fullUser = userMap.get(res.handle) || {};
        return {
          handle: res.handle,
          name: res.name,
          supply_enabled: res.supply_enabled,
          daily_target: res.daily_target || 30,
          role_family: res.role_family,
          atlas_role_group: res.atlas_role_group,
          remote_preference: res.remote_preference,
          target_states: res.target_states || [],
          cooldown_companies_history: res.cooldown_companies_history || 0,
          raw_atlas_matching_jobs: res.raw_atlas_matching_jobs,
          cooldown_dropped_jobs: res.cooldown_dropped_jobs,
          eligible_unique_companies: res.eligible_unique_companies,
          can_fulfill_daily_quota: res.can_fulfill_daily_quota,
          days_of_supply_runway: res.days_of_supply_runway,
          target_titles: fullUser.target_titles || [],
          locations: fullUser.locations || [],
          all_excluded_companies: fullUser.all_excluded_companies || []
        };
      });

      return NextResponse.json({
        status: "success",
        total_candidates: candidates.length,
        quota_pass_rate_pct: simData.pass_rate_pct,
        average_runway_days: simData.average_runway_days,
        tested_at: simData.tested_at,
        data: candidates
      });
    }

    return NextResponse.json(
      { status: "error", message: "Candidate simulation data not found." },
      { status: 404 }
    );
  } catch (error: any) {
    return NextResponse.json(
      { status: "error", message: error.message },
      { status: 500 }
    );
  }
}
