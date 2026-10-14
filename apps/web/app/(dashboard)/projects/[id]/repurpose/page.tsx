"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, ApiError } from "@/lib/api/client";
import { MediaAsset, Platform, PlatformLimit, SocialPost } from "@/lib/api/types";

const PLATFORMS: Platform[] = ["instagram", "tiktok", "facebook", "x"];
const PLATFORM_LABELS: Record<Platform, string> = {
  instagram: "Instagram",
  tiktok: "TikTok",
  facebook: "Facebook",
  x: "X",
};

/** FR-010 (Repurpose) + FR-026 (platform checks, enforced server-side on save). */
export default function RepurposePage() {
  const params = useParams<{ id: string }>();
  const projectId = params.id;

  const [posts, setPosts] = useState<SocialPost[] | null>(null);
  const [limits, setLimits] = useState<PlatformLimit[] | null>(null);
  const [assets, setAssets] = useState<MediaAsset[] | null>(null);
  const [selectedPlatforms, setSelectedPlatforms] = useState<Set<Platform>>(new Set(PLATFORMS));
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Record<string, { caption: string; hashtags: string; cta: string }>>(
    {},
  );

  const load = useCallback(async () => {
    try {
      const [p, l, a] = await Promise.all([
        api.get<SocialPost[]>(`/api/projects/${projectId}/posts`),
        api.get<PlatformLimit[]>("/api/platform-limits"),
        api.get<MediaAsset[]>(`/api/projects/${projectId}/media`),
      ]);
      setPosts(p);
      setLimits(l);
      setAssets(a);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't load this project's posts.");
    }
  }, [projectId]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
  }, [load]);

  function draftFor(post: SocialPost) {
    return (
      drafts[post.id] ?? {
        caption: post.caption ?? "",
        hashtags: post.hashtags.join(" "),
        cta: post.cta ?? "",
      }
    );
  }

  async function run(action: string, fn: () => Promise<unknown>) {
    setBusy(action);
    setError(null);
    try {
      await fn();
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setBusy(null);
    }
  }

  if (error && posts === null) {
    return (
      <p role="alert" className="text-sm text-red-600 dark:text-red-400">
        {error}
      </p>
    );
  }

  if (posts === null || limits === null || assets === null) {
    return <p className="text-sm text-black/60 dark:text-white/60">Loading…</p>;
  }

  const readyAssets = assets.filter((a) => a.status === "ready");

  return (
    <div className="space-y-8">
      <h1 className="text-xl font-semibold">Repurpose</h1>

      {error && (
        <p role="alert" className="text-sm text-red-600 dark:text-red-400">
          {error}
        </p>
      )}

      <section className="space-y-3">
        <div className="flex flex-wrap gap-3">
          {PLATFORMS.map((platform) => (
            <label key={platform} className="flex items-center gap-1 text-sm">
              <input
                type="checkbox"
                checked={selectedPlatforms.has(platform)}
                onChange={(e) => {
                  const next = new Set(selectedPlatforms);
                  if (e.target.checked) next.add(platform);
                  else next.delete(platform);
                  setSelectedPlatforms(next);
                }}
              />
              {PLATFORM_LABELS[platform]}
            </label>
          ))}
        </div>
        <button
          type="button"
          disabled={busy !== null || selectedPlatforms.size === 0}
          onClick={() =>
            run("generate", () =>
              api.post(`/api/projects/${projectId}/repurpose`, {
                platforms: Array.from(selectedPlatforms),
              }),
            )
          }
          className="rounded bg-black px-3 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-black"
        >
          {busy === "generate" ? "Generating…" : "Generate captions"}
        </button>
      </section>

      {posts.length === 0 ? (
        <p className="text-sm text-black/60 dark:text-white/60">
          No platform posts yet — generate captions above.
        </p>
      ) : (
        <ul className="space-y-6">
          {posts.map((post) => {
            const limit = limits.find((l) => l.platform === post.platform);
            const draft = draftFor(post);
            const maxChars = limit?.caption_max_chars ?? 0;
            const remaining = maxChars - draft.caption.length;

            return (
              <li key={post.id} className="space-y-2 rounded border border-black/10 p-4 dark:border-white/10">
                <div className="flex items-center justify-between">
                  <h2 className="font-medium">{PLATFORM_LABELS[post.platform]}</h2>
                  <span
                    className={`text-xs ${remaining < 0 ? "text-red-600 dark:text-red-400" : "text-black/60 dark:text-white/60"}`}
                  >
                    {remaining} characters left
                  </span>
                </div>

                <textarea
                  value={draft.caption}
                  onChange={(e) =>
                    setDrafts((d) => ({ ...d, [post.id]: { ...draft, caption: e.target.value } }))
                  }
                  rows={3}
                  className="w-full rounded border border-black/20 px-3 py-2 text-sm dark:border-white/20 dark:bg-transparent"
                />
                <input
                  value={draft.hashtags}
                  onChange={(e) =>
                    setDrafts((d) => ({ ...d, [post.id]: { ...draft, hashtags: e.target.value } }))
                  }
                  placeholder="#hashtags separated by spaces"
                  className="w-full rounded border border-black/20 px-3 py-2 text-sm dark:border-white/20 dark:bg-transparent"
                />
                <input
                  value={draft.cta}
                  onChange={(e) => setDrafts((d) => ({ ...d, [post.id]: { ...draft, cta: e.target.value } }))}
                  placeholder="Call to action"
                  className="w-full rounded border border-black/20 px-3 py-2 text-sm dark:border-white/20 dark:bg-transparent"
                />

                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    disabled={busy !== null}
                    onClick={() =>
                      run(`save-${post.id}`, () =>
                        api.patch(`/api/posts/${post.id}`, {
                          caption: draft.caption,
                          hashtags: draft.hashtags.split(/\s+/).filter(Boolean),
                          cta: draft.cta,
                        }),
                      )
                    }
                    className="rounded border border-black/20 px-2 py-1 text-xs disabled:opacity-50 dark:border-white/20"
                  >
                    Save
                  </button>

                  {readyAssets.length > 0 && (
                    <select
                      defaultValue={post.media_asset_id ?? ""}
                      onChange={(e) =>
                        e.target.value &&
                        run(`attach-${post.id}`, () =>
                          api.patch(`/api/posts/${post.id}`, { media_asset_id: e.target.value }),
                        )
                      }
                      className="rounded border border-black/20 px-2 py-1 text-xs dark:border-white/20 dark:bg-transparent"
                    >
                      <option value="">Attach export…</option>
                      {readyAssets.map((a) => (
                        <option key={a.id} value={a.id}>
                          {a.kind} ({a.duration_seconds ? `${Math.round(a.duration_seconds)}s` : "?"})
                        </option>
                      ))}
                    </select>
                  )}

                  <span className="text-xs text-black/60 dark:text-white/60">{post.status}</span>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
