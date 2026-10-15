"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api/client";
import { WeeklyReview } from "@/lib/api/types";

/** FR-019 — on-demand weekly report: best/worst posts, platform changes,
 * data gaps, 1-3 suggested experiments, no causal claims. */
export default function WeeklyReviewPage() {
  const [review, setReview] = useState<WeeklyReview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setReview(await api.get<WeeklyReview>("/api/reports/weekly"));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't load the weekly review.");
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
  }, [load]);

  async function markComplete() {
    if (!review) return;
    setBusy(true);
    try {
      await api.post(`/api/reports/weekly/${review.id}/complete`);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't mark this review complete.");
    } finally {
      setBusy(false);
    }
  }

  if (error && review === null) {
    return (
      <p role="alert" className="text-sm text-red-600 dark:text-red-400">
        {error}
      </p>
    );
  }

  if (review === null) {
    return <p className="text-sm text-black/60 dark:text-white/60">Loading…</p>;
  }

  const report = review.report_json;

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Weekly review — {report.week_start}</h1>
        {review.reviewed_at ? (
          <span className="text-sm text-green-700 dark:text-green-400">
            Reviewed {new Date(review.reviewed_at).toLocaleDateString("en-GB")}
          </span>
        ) : (
          <button
            type="button"
            disabled={busy}
            onClick={markComplete}
            className="rounded bg-black px-3 py-1 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-black"
          >
            Mark complete
          </button>
        )}
      </div>

      {error && (
        <p role="alert" className="text-sm text-red-600 dark:text-red-400">
          {error}
        </p>
      )}

      <section className="space-y-2">
        <h2 className="font-medium">Best posts</h2>
        {report.best_posts.length === 0 ? (
          <p className="text-sm text-black/60 dark:text-white/60">
            No posts with metrics yet this week.
          </p>
        ) : (
          <ul className="space-y-1 text-sm">
            {report.best_posts.map((p) => (
              <li key={p.post_id}>
                {p.platform} — {p.caption?.slice(0, 60) ?? p.post_id} ({p.reach} reach)
              </li>
            ))}
          </ul>
        )}
      </section>

      {report.worst_posts.length > 0 && (
        <section className="space-y-2">
          <h2 className="font-medium">Worst posts</h2>
          <ul className="space-y-1 text-sm">
            {report.worst_posts.map((p) => (
              <li key={p.post_id}>
                {p.platform} — {p.caption?.slice(0, 60) ?? p.post_id} ({p.reach} reach)
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="space-y-2">
        <h2 className="font-medium">Platform changes</h2>
        {Object.keys(report.platform_changes).length === 0 ? (
          <p className="text-sm text-black/60 dark:text-white/60">Not enough data yet.</p>
        ) : (
          <ul className="space-y-1 text-sm">
            {Object.entries(report.platform_changes).map(([platform, change]) => (
              <li key={platform}>
                {platform}: reach median {change.reach_median_current ?? "Unavailable"} (was{" "}
                {change.reach_median_previous ?? "Unavailable"})
              </li>
            ))}
          </ul>
        )}
      </section>

      {report.data_gaps.length > 0 && (
        <section className="space-y-2">
          <h2 className="font-medium">Data gaps</h2>
          <ul className="list-disc space-y-1 pl-5 text-sm text-yellow-700 dark:text-yellow-400">
            {report.data_gaps.map((gap, i) => (
              <li key={i}>{gap}</li>
            ))}
          </ul>
        </section>
      )}

      <section className="space-y-2">
        <h2 className="font-medium">Suggested experiments</h2>
        {report.suggested_experiments.length === 0 ? (
          <p className="text-sm text-black/60 dark:text-white/60">None yet.</p>
        ) : (
          <ul className="space-y-2 text-sm">
            {report.suggested_experiments.map((s, i) => (
              <li key={i} className="rounded border border-black/10 p-2 dark:border-white/10">
                {s.hypothesis}
              </li>
            ))}
          </ul>
        )}
      </section>

      <p className="text-xs text-black/40 dark:text-white/40">{report.disclaimer}</p>
    </div>
  );
}
