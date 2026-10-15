"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, ApiError } from "@/lib/api/client";
import { HomeDashboard, Platform, PROJECT_STATES, ProjectState } from "@/lib/api/types";

const STATE_LABELS: Record<ProjectState, string> = {
  idea: "Idea",
  scripting: "Scripting",
  script_approved: "Script approved",
  recorded: "Recorded",
  subtitled: "Subtitled",
  ready: "Ready",
  scheduled: "Scheduled",
  published: "Published",
  measured: "Measured",
};

const PLATFORMS: Platform[] = ["instagram", "tiktok", "facebook", "x"];

/** FR-025 Home dashboard. */
export default function DashboardPage() {
  const [data, setData] = useState<HomeDashboard | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<HomeDashboard>("/api/dashboard/home")
      .then(setData)
      .catch((err: ApiError) => setError(err.message));
  }, []);

  if (error) {
    return (
      <p role="alert" className="text-sm text-red-600 dark:text-red-400">
        Couldn&apos;t load your dashboard: {error}
      </p>
    );
  }

  if (data === null) {
    return <p className="text-sm text-black/60 dark:text-white/60">Loading…</p>;
  }

  const pipeline = PROJECT_STATES.map((state) => ({
    state,
    count: data.pipeline_counts[state] ?? 0,
  }));
  const totalProjects = pipeline.reduce((sum, p) => sum + p.count, 0);

  return (
    <div className="space-y-8">
      <h1 className="text-xl font-semibold">Home</h1>

      <section className="space-y-3">
        <h2 className="font-medium">Next actions</h2>
        {data.next_actions.length === 0 ? (
          <div className="rounded border border-dashed border-black/20 p-6 text-center dark:border-white/20">
            <p className="text-sm text-black/60 dark:text-white/60">No active projects yet.</p>
            <Link href="/projects" className="mt-2 inline-block text-sm font-medium underline">
              Create your first project
            </Link>
          </div>
        ) : (
          <ul className="space-y-2">
            {data.next_actions.map((a) => (
              <li
                key={a.project_id}
                className="flex items-center justify-between rounded border border-black/10 p-3 text-sm dark:border-white/10"
              >
                <Link href={`/projects/${a.project_id}`} className="font-medium hover:underline">
                  {a.title}
                </Link>
                <span className="text-black/60 dark:text-white/60">{a.next_action}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      {totalProjects > 0 && (
        <section className="space-y-3">
          <h2 className="font-medium">Pipeline</h2>
          <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            {pipeline.map(({ state, count }) => (
              <li key={state} className="rounded border border-black/10 p-3 dark:border-white/10">
                <p className="text-2xl font-semibold">{count}</p>
                <p className="text-sm text-black/60 dark:text-white/60">{STATE_LABELS[state]}</p>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="space-y-3">
        <h2 className="font-medium">Posting adherence</h2>
        <div className="flex gap-6 text-sm">
          <Adherence label="This week" value={data.posting_adherence_this_week} />
          <Adherence label="Last week" value={data.posting_adherence_last_week} />
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="font-medium">Reach and follower trends</h2>
        <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {PLATFORMS.map((platform) => {
            const reach = data.reach_trend[platform] ?? [];
            const followers = data.follower_trend[platform] ?? [];
            const lastSnapshot = data.last_follower_snapshot_at[platform];
            return (
              <li key={platform} className="rounded border border-black/10 p-3 dark:border-white/10">
                <p className="text-sm font-medium capitalize">{platform}</p>
                <p className="mt-1 text-xs text-black/60 dark:text-white/60">
                  Reach (day 7)
                  <Sparkline values={reach.map((p) => p.reach ?? null)} />
                </p>
                <p className="mt-2 text-xs text-black/60 dark:text-white/60">
                  Followers
                  <Sparkline values={followers.map((p) => p.follower_count ?? null)} />
                </p>
                <p className="mt-1 text-xs text-black/40 dark:text-white/40">
                  {lastSnapshot
                    ? `Last follower snapshot: ${new Date(lastSnapshot).toLocaleDateString("en-GB")}`
                    : "No follower snapshot yet"}
                </p>
              </li>
            );
          })}
        </ul>
      </section>
    </div>
  );
}

function Adherence({ label, value }: { label: string; value: number | null }) {
  return (
    <div>
      <p className="text-2xl font-semibold">{value === null ? "—" : `${Math.round(value * 100)}%`}</p>
      <p className="text-black/60 dark:text-white/60">{label}</p>
    </div>
  );
}

function Sparkline({ values }: { values: (number | null)[] }) {
  const points = values.filter((v): v is number => v !== null);
  if (points.length < 2) {
    return <span className="ml-1 text-black/40 dark:text-white/40">Not enough data yet</span>;
  }

  const width = 100;
  const height = 24;
  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = max - min || 1;
  const step = width / (points.length - 1);
  const coords = points
    .map((v, i) => `${(i * step).toFixed(1)},${(height - ((v - min) / range) * height).toFixed(1)}`)
    .join(" ");

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="mt-0.5 h-6 w-28" aria-hidden="true">
      <polyline points={coords} fill="none" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}
