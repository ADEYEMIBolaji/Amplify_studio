"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api/client";
import {
  AnalyticsOverview,
  FollowerSnapshot,
  Platform,
  PlatformPeriodMetrics,
  Recommendations,
  SocialPost,
} from "@/lib/api/types";

const PLATFORMS: Platform[] = ["instagram", "tiktok", "facebook", "x"];
const RANGES = [7, 28, 90];

/** FR-013/014 (manual metrics), FR-015/016 (calculations + dashboard),
 * FR-028 (historical import), FR-029 (follower snapshots). */
export default function GrowthLabPage() {
  const [platform, setPlatform] = useState<Platform>("instagram");
  const [rangeDays, setRangeDays] = useState(28);
  const [overview, setOverview] = useState<AnalyticsOverview | null>(null);
  const [recommendations, setRecommendations] = useState<Recommendations | null>(null);
  const [posts, setPosts] = useState<SocialPost[] | null>(null);
  const [followerSnapshots, setFollowerSnapshots] = useState<FollowerSnapshot[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const loadOverview = useCallback(async () => {
    try {
      setOverview(await api.get(`/api/analytics/overview?platform=${platform}&range_days=${rangeDays}`));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't load analytics.");
    }
  }, [platform, rangeDays]);

  const loadRecommendations = useCallback(async () => {
    try {
      setRecommendations(await api.get(`/api/analytics/recommendations?platform=${platform}`));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't load recommendations.");
    }
  }, [platform]);

  const loadPosts = useCallback(async () => {
    try {
      setPosts(await api.get<SocialPost[]>("/api/calendar"));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't load posts.");
    }
  }, []);

  const loadFollowerSnapshots = useCallback(async () => {
    try {
      setFollowerSnapshots(await api.get<FollowerSnapshot[]>(`/api/follower-snapshots?platform=${platform}`));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't load follower snapshots.");
    }
  }, [platform]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadOverview();
  }, [loadOverview]);
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadRecommendations();
  }, [loadRecommendations]);
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadPosts();
  }, [loadPosts]);
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadFollowerSnapshots();
  }, [loadFollowerSnapshots]);

  return (
    <div className="space-y-10">
      <h1 className="text-xl font-semibold">Growth Lab</h1>

      {error && (
        <p role="alert" className="text-sm text-red-600 dark:text-red-400">
          {error}
        </p>
      )}
      {notice && <p className="text-sm text-green-700 dark:text-green-400">{notice}</p>}

      <section className="space-y-3">
        <div className="flex flex-wrap gap-3">
          <select
            value={platform}
            onChange={(e) => setPlatform(e.target.value as Platform)}
            className="rounded border border-black/20 px-2 py-1 text-sm dark:border-white/20 dark:bg-transparent"
          >
            {PLATFORMS.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
          <div className="flex gap-1">
            {RANGES.map((r) => (
              <button
                key={r}
                onClick={() => setRangeDays(r)}
                className={`rounded border px-2 py-1 text-xs ${
                  rangeDays === r
                    ? "border-black bg-black text-white dark:border-white dark:bg-white dark:text-black"
                    : "border-black/20 dark:border-white/20"
                }`}
              >
                {r}d
              </button>
            ))}
          </div>
        </div>

        {overview === null ? (
          <p className="text-sm text-black/60 dark:text-white/60">Loading…</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-black/60 dark:text-white/60">
                  <th className="pr-4 font-normal">Metric</th>
                  <th className="pr-4 font-normal">Current</th>
                  <th className="font-normal">Previous</th>
                </tr>
              </thead>
              <tbody>
                <MetricRow label="Reach (median)" current={overview.current} previous={overview.previous} field="reach_median" />
                <MetricRow label="Engagement / reach" current={overview.current} previous={overview.previous} field="engagement_per_reach" pct />
                <MetricRow label="Share rate" current={overview.current} previous={overview.previous} field="share_rate" pct />
                <MetricRow label="Save rate" current={overview.current} previous={overview.previous} field="save_rate" pct />
                <MetricRow label="Net follower change" current={overview.current} previous={overview.previous} field="net_follower_change" />
                <MetricRow label="Followers / 1,000 reached" current={overview.current} previous={overview.previous} field="followers_per_1000_reached" />
                <MetricRow label="Posting adherence" current={overview.current} previous={overview.previous} field="posting_adherence" pct />
              </tbody>
            </table>
            <p className="mt-2 text-xs text-black/60 dark:text-white/60">
              Data coverage: {overview.current.data_coverage.eligible} of {overview.current.data_coverage.total}{" "}
              posts had a day-{overview.current.target_day} snapshot.
              {overview.current.low_sample && " Low sample size — treat this range with caution."}
              {overview.current.net_follower_change_low_confidence &&
                " Follower change is low-confidence (snapshot more than 2 days from the period boundary)."}
            </p>
          </div>
        )}
      </section>

      <section className="space-y-3">
        <h2 className="font-medium">Recommendations</h2>
        {recommendations === null ? (
          <p className="text-sm text-black/60 dark:text-white/60">Loading…</p>
        ) : (
          <div className="space-y-3">
            {recommendations.consistency_warning && (
              <p className="rounded border border-yellow-600/30 bg-yellow-50 p-2 text-sm text-yellow-800 dark:bg-yellow-900/20 dark:text-yellow-300">
                {recommendations.consistency_warning}
              </p>
            )}

            {recommendations.comparisons.length === 0 &&
              recommendations.insufficient_data.length === 0 &&
              recommendations.high_savers.length === 0 &&
              recommendations.underperformers.length === 0 &&
              !recommendations.consistency_warning && (
                <p className="text-sm text-black/60 dark:text-white/60">
                  Nothing to report yet for {platform}.
                </p>
              )}

            {recommendations.comparisons.map((c, i) => (
              <div key={i} className="rounded border border-green-600/30 bg-green-50 p-3 text-sm dark:bg-green-900/20">
                <p>{c.summary}</p>
              </div>
            ))}

            {recommendations.insufficient_data.map((d, i) => (
              <p key={i} className="text-sm text-black/60 dark:text-white/60">
                Not enough data yet to compare {d.dimension} groups — need {d.posts_still_needed} more post(s)
                in a group (have: {Object.entries(d.group_counts).map(([k, v]) => `${k}=${v}`).join(", ")}).
              </p>
            ))}

            {recommendations.high_savers.map((h) => (
              <p key={h.post_id} className="text-sm text-black/80 dark:text-white/80">
                {h.summary}
              </p>
            ))}

            {recommendations.underperformers.map((h) => (
              <p key={h.post_id} className="text-sm text-black/80 dark:text-white/80">
                {h.summary}
              </p>
            ))}
          </div>
        )}
      </section>

      <ManualMetricForm
        posts={posts}
        onSaved={() => {
          setNotice("Metric saved.");
          loadOverview();
        }}
        onError={setError}
      />

      <FollowerSnapshotForm
        platform={platform}
        snapshots={followerSnapshots}
        onSaved={() => {
          setNotice("Follower snapshot saved.");
          loadFollowerSnapshots();
          loadOverview();
        }}
        onError={setError}
      />

      <HistoricalImportForm
        onSaved={() => {
          setNotice("Historical post imported.");
          loadPosts();
          loadOverview();
        }}
        onError={setError}
      />
    </div>
  );
}

function MetricRow({
  label,
  current,
  previous,
  field,
  pct = false,
}: {
  label: string;
  current: PlatformPeriodMetrics;
  previous: PlatformPeriodMetrics;
  field: keyof PlatformPeriodMetrics;
  pct?: boolean;
}) {
  const format = (v: unknown) => {
    if (v === null || v === undefined) return "Unavailable";
    const n = v as number;
    return pct ? `${(n * 100).toFixed(1)}%` : n.toFixed(1);
  };
  return (
    <tr className="border-t border-black/10 dark:border-white/10">
      <td className="py-1 pr-4">{label}</td>
      <td className="py-1 pr-4">{format(current[field])}</td>
      <td className="py-1 text-black/60 dark:text-white/60">{format(previous[field])}</td>
    </tr>
  );
}

function ManualMetricForm({
  posts,
  onSaved,
  onError,
}: {
  posts: SocialPost[] | null;
  onSaved: () => void;
  onError: (msg: string) => void;
}) {
  const [postId, setPostId] = useState("");
  const [capturedAt, setCapturedAt] = useState("");
  const [reach, setReach] = useState("");
  const [saving, setSaving] = useState(false);
  const [duplicateChoice, setDuplicateChoice] = useState(false);

  async function submit(onDuplicate?: "update" | "skip") {
    if (!postId || !capturedAt) return;
    setSaving(true);
    try {
      await api.post("/api/metrics/manual", {
        social_post_id: postId,
        captured_at: new Date(capturedAt).toISOString(),
        reach: reach ? Number(reach) : null,
        on_duplicate: onDuplicate,
      });
      setDuplicateChoice(false);
      onSaved();
    } catch (err) {
      if (err instanceof ApiError && err.code === "duplicate_snapshot") {
        setDuplicateChoice(true);
      } else {
        onError(err instanceof ApiError ? err.message : "Couldn't save the metric.");
      }
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="space-y-3">
      <h2 className="font-medium">Add metrics manually</h2>
      <div className="flex flex-wrap gap-2">
        <select
          value={postId}
          onChange={(e) => setPostId(e.target.value)}
          className="rounded border border-black/20 px-2 py-1 text-sm dark:border-white/20 dark:bg-transparent"
        >
          <option value="">Select a post…</option>
          {(posts ?? []).map((p) => (
            <option key={p.id} value={p.id}>
              {p.platform} — {p.caption?.slice(0, 40) ?? p.id}
            </option>
          ))}
        </select>
        <input
          type="date"
          value={capturedAt}
          onChange={(e) => setCapturedAt(e.target.value)}
          className="rounded border border-black/20 px-2 py-1 text-sm dark:border-white/20 dark:bg-transparent"
        />
        <input
          type="number"
          min={0}
          placeholder="Reach"
          value={reach}
          onChange={(e) => setReach(e.target.value)}
          className="w-24 rounded border border-black/20 px-2 py-1 text-sm dark:border-white/20 dark:bg-transparent"
        />
        <button
          type="button"
          disabled={saving || !postId || !capturedAt}
          onClick={() => submit()}
          className="rounded bg-black px-3 py-1 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-black"
        >
          Save
        </button>
      </div>
      {duplicateChoice && (
        <div className="flex items-center gap-2 text-xs">
          <span>A snapshot already exists for this post on this date.</span>
          <button onClick={() => submit("update")} className="rounded border border-black/20 px-2 py-0.5 dark:border-white/20">
            Update it
          </button>
          <button onClick={() => submit("skip")} className="rounded border border-black/20 px-2 py-0.5 dark:border-white/20">
            Skip
          </button>
        </div>
      )}
    </section>
  );
}

function FollowerSnapshotForm({
  platform,
  snapshots,
  onSaved,
  onError,
}: {
  platform: Platform;
  snapshots: FollowerSnapshot[] | null;
  onSaved: () => void;
  onError: (msg: string) => void;
}) {
  const [capturedAt, setCapturedAt] = useState("");
  const [followerCount, setFollowerCount] = useState("");
  const [saving, setSaving] = useState(false);

  async function submit() {
    setSaving(true);
    try {
      await api.post("/api/follower-snapshots", {
        platform,
        captured_at: new Date(capturedAt).toISOString(),
        follower_count: Number(followerCount),
      });
      setCapturedAt("");
      setFollowerCount("");
      onSaved();
    } catch (err) {
      onError(err instanceof ApiError ? err.message : "Couldn't save the follower snapshot.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="space-y-3">
      <h2 className="font-medium">Follower snapshot ({platform})</h2>
      <div className="flex flex-wrap gap-2">
        <input
          type="date"
          value={capturedAt}
          onChange={(e) => setCapturedAt(e.target.value)}
          className="rounded border border-black/20 px-2 py-1 text-sm dark:border-white/20 dark:bg-transparent"
        />
        <input
          type="number"
          min={0}
          placeholder="Follower count"
          value={followerCount}
          onChange={(e) => setFollowerCount(e.target.value)}
          className="w-36 rounded border border-black/20 px-2 py-1 text-sm dark:border-white/20 dark:bg-transparent"
        />
        <button
          type="button"
          disabled={saving || !capturedAt || !followerCount}
          onClick={submit}
          className="rounded bg-black px-3 py-1 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-black"
        >
          Save
        </button>
      </div>
      {snapshots !== null && (
        <p className="text-xs text-black/60 dark:text-white/60">
          {snapshots.length === 0
            ? "No snapshots yet."
            : `Last: ${new Date(snapshots[0].captured_at).toLocaleDateString("en-GB")} — ${snapshots[0].follower_count}`}
        </p>
      )}
    </section>
  );
}

function HistoricalImportForm({
  onSaved,
  onError,
}: {
  onSaved: () => void;
  onError: (msg: string) => void;
}) {
  const [platform, setPlatform] = useState<Platform>("instagram");
  const [url, setUrl] = useState("");
  const [publishedAt, setPublishedAt] = useState("");
  const [saving, setSaving] = useState(false);

  async function submit() {
    setSaving(true);
    try {
      await api.post("/api/posts/historical", {
        platform,
        external_url: url,
        published_at: new Date(publishedAt).toISOString(),
      });
      setUrl("");
      setPublishedAt("");
      onSaved();
    } catch (err) {
      onError(err instanceof ApiError ? err.message : "Couldn't import this post.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="space-y-3">
      <h2 className="font-medium">Import a historical post</h2>
      <p className="text-xs text-black/60 dark:text-white/60">
        Posts published before Amplify Studio — no project required (FR-028).
      </p>
      <div className="flex flex-wrap gap-2">
        <select
          value={platform}
          onChange={(e) => setPlatform(e.target.value as Platform)}
          className="rounded border border-black/20 px-2 py-1 text-sm dark:border-white/20 dark:bg-transparent"
        >
          {PLATFORMS.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
        <input
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="Live post URL"
          className="min-w-56 rounded border border-black/20 px-2 py-1 text-sm dark:border-white/20 dark:bg-transparent"
        />
        <input
          type="date"
          value={publishedAt}
          onChange={(e) => setPublishedAt(e.target.value)}
          className="rounded border border-black/20 px-2 py-1 text-sm dark:border-white/20 dark:bg-transparent"
        />
        <button
          type="button"
          disabled={saving || !url || !publishedAt}
          onClick={submit}
          className="rounded bg-black px-3 py-1 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-black"
        >
          Import
        </button>
      </div>
    </section>
  );
}
