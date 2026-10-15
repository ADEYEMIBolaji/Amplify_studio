"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api/client";
import { Experiment, SocialPost } from "@/lib/api/types";

const VARIABLES = ["hook", "topic", "length", "cta", "posting_slot"];

/** FR-018 — hypothesis, one primary variable, comparison posts, confounders,
 * Owner-recorded outcome. */
export default function ExperimentsPage() {
  const [experiments, setExperiments] = useState<Experiment[] | null>(null);
  const [posts, setPosts] = useState<SocialPost[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const [hypothesis, setHypothesis] = useState("");
  const [variable, setVariable] = useState("hook");
  const [metric, setMetric] = useState("share_rate");
  const [selectedPosts, setSelectedPosts] = useState<Set<string>>(new Set());

  const load = useCallback(async () => {
    try {
      const [exps, allPosts] = await Promise.all([
        api.get<Experiment[]>("/api/experiments"),
        api.get<SocialPost[]>("/api/calendar"),
      ]);
      setExperiments(exps);
      setPosts(allPosts);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't load experiments.");
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
  }, [load]);

  async function createExperiment() {
    setBusy("create");
    setError(null);
    try {
      await api.post("/api/experiments", {
        hypothesis,
        variable,
        metric,
        post_ids: Array.from(selectedPosts),
      });
      setHypothesis("");
      setSelectedPosts(new Set());
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't create the experiment.");
    } finally {
      setBusy(null);
    }
  }

  async function recordOutcome(id: string, outcome: string, note: string) {
    setBusy(id);
    try {
      await api.patch(`/api/experiments/${id}`, { outcome, outcome_note: note });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't save the outcome.");
    } finally {
      setBusy(null);
    }
  }

  if (error && experiments === null) {
    return (
      <p role="alert" className="text-sm text-red-600 dark:text-red-400">
        {error}
      </p>
    );
  }

  if (experiments === null || posts === null) {
    return <p className="text-sm text-black/60 dark:text-white/60">Loading…</p>;
  }

  return (
    <div className="space-y-8">
      <h1 className="text-xl font-semibold">Experiments</h1>

      {error && (
        <p role="alert" className="text-sm text-red-600 dark:text-red-400">
          {error}
        </p>
      )}

      <section className="space-y-3 rounded border border-black/10 p-4 dark:border-white/10">
        <h2 className="text-sm font-medium">New experiment</h2>
        <textarea
          value={hypothesis}
          onChange={(e) => setHypothesis(e.target.value)}
          placeholder="Hypothesis"
          rows={2}
          className="w-full rounded border border-black/20 px-2 py-1 text-sm dark:border-white/20 dark:bg-transparent"
        />
        <div className="flex flex-wrap gap-2">
          <select
            value={variable}
            onChange={(e) => setVariable(e.target.value)}
            className="rounded border border-black/20 px-2 py-1 text-sm dark:border-white/20 dark:bg-transparent"
          >
            {VARIABLES.map((v) => (
              <option key={v} value={v}>
                {v}
              </option>
            ))}
          </select>
          <input
            value={metric}
            onChange={(e) => setMetric(e.target.value)}
            placeholder="Metric (e.g. share_rate)"
            className="rounded border border-black/20 px-2 py-1 text-sm dark:border-white/20 dark:bg-transparent"
          />
        </div>
        <div className="max-h-40 overflow-y-auto rounded border border-black/10 p-2 text-xs dark:border-white/10">
          {posts.map((p) => (
            <label key={p.id} className="flex items-center gap-2 py-0.5">
              <input
                type="checkbox"
                checked={selectedPosts.has(p.id)}
                onChange={(e) => {
                  const next = new Set(selectedPosts);
                  if (e.target.checked) next.add(p.id);
                  else next.delete(p.id);
                  setSelectedPosts(next);
                }}
              />
              {p.platform} — {p.caption?.slice(0, 50) ?? p.id}
            </label>
          ))}
        </div>
        <button
          type="button"
          disabled={busy === "create" || !hypothesis || selectedPosts.size < 2}
          onClick={createExperiment}
          className="rounded bg-black px-3 py-1 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-black"
        >
          Create experiment
        </button>
      </section>

      {experiments.length === 0 ? (
        <p className="text-sm text-black/60 dark:text-white/60">No experiments yet.</p>
      ) : (
        <ul className="space-y-4">
          {experiments.map((exp) => (
            <li key={exp.id} className="rounded border border-black/10 p-4 text-sm dark:border-white/10">
              <p className="font-medium">{exp.hypothesis}</p>
              <p className="mt-1 text-xs text-black/60 dark:text-white/60">
                Variable: {exp.variable} · Metric: {exp.metric} · {exp.post_ids.length} posts
              </p>
              {exp.confounders.length > 0 && (
                <p className="mt-1 text-xs text-yellow-700 dark:text-yellow-400">
                  Possible confounders: {exp.confounders.join(", ")}
                </p>
              )}
              {exp.outcome ? (
                <p className="mt-2 text-xs">
                  Outcome: <span className="font-medium">{exp.outcome.replace("_", " ")}</span>
                  {exp.outcome_note && ` — ${exp.outcome_note}`}
                </p>
              ) : (
                <OutcomeForm experimentId={exp.id} busy={busy === exp.id} onSave={recordOutcome} />
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function OutcomeForm({
  experimentId,
  busy,
  onSave,
}: {
  experimentId: string;
  busy: boolean;
  onSave: (id: string, outcome: string, note: string) => void;
}) {
  const [outcome, setOutcome] = useState("supported");
  const [note, setNote] = useState("");

  return (
    <div className="mt-2 flex flex-wrap items-center gap-2">
      <select
        value={outcome}
        onChange={(e) => setOutcome(e.target.value)}
        className="rounded border border-black/20 px-2 py-0.5 text-xs dark:border-white/20 dark:bg-transparent"
      >
        <option value="supported">Supported</option>
        <option value="not_supported">Not supported</option>
        <option value="inconclusive">Inconclusive</option>
      </select>
      <input
        value={note}
        onChange={(e) => setNote(e.target.value)}
        placeholder="Note"
        className="rounded border border-black/20 px-2 py-0.5 text-xs dark:border-white/20 dark:bg-transparent"
      />
      <button
        type="button"
        disabled={busy}
        onClick={() => onSave(experimentId, outcome, note)}
        className="rounded border border-black/20 px-2 py-0.5 text-xs disabled:opacity-50 dark:border-white/20"
      >
        Record outcome
      </button>
    </div>
  );
}
