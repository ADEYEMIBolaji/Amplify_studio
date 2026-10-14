"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, ApiError } from "@/lib/api/client";
import type { Project } from "@/lib/api/types";

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [topic, setTopic] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  function load() {
    api
      .get<Project[]>("/api/projects")
      .then(setProjects)
      .catch((err: ApiError) => setError(err.message));
  }

  useEffect(load, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setCreating(true);
    setCreateError(null);
    try {
      await api.post("/api/projects", { title, topic });
      setTitle("");
      setTopic("");
      load();
    } catch (err) {
      setCreateError(err instanceof ApiError ? err.message : "Couldn't create the project.");
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-xl font-semibold">Projects</h1>
      </div>

      <form onSubmit={handleCreate} className="space-y-3 rounded border border-black/10 p-4 dark:border-white/10">
        <h2 className="text-sm font-medium">New project</h2>
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <label htmlFor="title" className="block text-sm">
              Title
            </label>
            <input
              id="title"
              required
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="mt-1 w-full rounded border border-black/20 px-3 py-2 text-sm dark:border-white/20 dark:bg-transparent"
            />
          </div>
          <div>
            <label htmlFor="topic" className="block text-sm">
              Topic
            </label>
            <input
              id="topic"
              required
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              className="mt-1 w-full rounded border border-black/20 px-3 py-2 text-sm dark:border-white/20 dark:bg-transparent"
            />
          </div>
        </div>
        {createError && (
          <p role="alert" className="text-sm text-red-600 dark:text-red-400">
            {createError}
          </p>
        )}
        <button
          type="submit"
          disabled={creating}
          className="rounded bg-black px-3 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-black"
        >
          {creating ? "Creating…" : "Create project"}
        </button>
      </form>

      {error && (
        <p role="alert" className="text-sm text-red-600 dark:text-red-400">
          Couldn&apos;t load projects: {error}
        </p>
      )}

      {projects === null && !error && (
        <p className="text-sm text-black/60 dark:text-white/60">Loading…</p>
      )}

      {projects !== null && projects.length === 0 && (
        <p className="text-sm text-black/60 dark:text-white/60">
          No projects yet — create one above.
        </p>
      )}

      {projects !== null && projects.length > 0 && (
        <ul className="divide-y divide-black/10 dark:divide-white/10">
          {projects.map((p) => (
            <li key={p.id} className="flex items-center justify-between py-3">
              <div>
                <Link href={`/projects/${p.id}`} className="font-medium hover:underline">
                  {p.title}
                </Link>
                <p className="text-sm text-black/60 dark:text-white/60">{p.topic}</p>
              </div>
              <span className="rounded-full border border-black/20 px-2 py-0.5 text-xs dark:border-white/20">
                {p.status.replace("_", " ")}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
