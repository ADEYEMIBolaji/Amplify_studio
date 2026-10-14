"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, ApiError } from "@/lib/api/client";
import { PROJECT_STATES, type Project, type ProjectState } from "@/lib/api/types";

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

export default function DashboardPage() {
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<Project[]>("/api/projects")
      .then(setProjects)
      .catch((err: ApiError) => setError(err.message));
  }, []);

  if (error) {
    return (
      <p role="alert" className="text-sm text-red-600 dark:text-red-400">
        Couldn&apos;t load your projects: {error}
      </p>
    );
  }

  if (projects === null) {
    return <p className="text-sm text-black/60 dark:text-white/60">Loading…</p>;
  }

  const byState = PROJECT_STATES.map((state) => ({
    state,
    count: projects.filter((p) => p.status === state).length,
  }));

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-xl font-semibold">Home</h1>
        <p className="mt-1 text-sm text-black/60 dark:text-white/60">
          Full home dashboard (next action, posting adherence, reach trends) ships in Week 5
          (FR-025). This is a pipeline-by-state placeholder for now.
        </p>
      </div>

      {projects.length === 0 ? (
        <div className="rounded border border-dashed border-black/20 p-6 text-center dark:border-white/20">
          <p className="text-sm text-black/60 dark:text-white/60">No projects yet.</p>
          <Link href="/projects" className="mt-2 inline-block text-sm font-medium underline">
            Create your first project
          </Link>
        </div>
      ) : (
        <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {byState.map(({ state, count }) => (
            <li
              key={state}
              className="rounded border border-black/10 p-3 dark:border-white/10"
            >
              <p className="text-2xl font-semibold">{count}</p>
              <p className="text-sm text-black/60 dark:text-white/60">{STATE_LABELS[state]}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
