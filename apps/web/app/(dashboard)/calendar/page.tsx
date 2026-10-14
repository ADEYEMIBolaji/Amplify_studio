"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api/client";
import { SocialPost } from "@/lib/api/types";

/** FR-011 (Calendar) + FR-012 (publication evidence) + FR-027 (reminders,
 * created server-side when a post is scheduled — nothing to show here). */
export default function CalendarPage() {
  const [posts, setPosts] = useState<SocialPost[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [scheduleDrafts, setScheduleDrafts] = useState<Record<string, { local: string; tz: string }>>({});
  const [publishDrafts, setPublishDrafts] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    try {
      setPosts(await api.get<SocialPost[]>("/api/calendar"));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't load the calendar.");
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
  }, [load]);

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

  function formatLocal(post: SocialPost): string {
    if (!post.scheduled_at) return "Not scheduled";
    try {
      return new Intl.DateTimeFormat("en-GB", {
        dateStyle: "medium",
        timeStyle: "short",
        timeZone: post.timezone,
      }).format(new Date(post.scheduled_at));
    } catch {
      return post.scheduled_at;
    }
  }

  if (error && posts === null) {
    return (
      <p role="alert" className="text-sm text-red-600 dark:text-red-400">
        {error}
      </p>
    );
  }

  if (posts === null) {
    return <p className="text-sm text-black/60 dark:text-white/60">Loading…</p>;
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Calendar</h1>

      {error && (
        <p role="alert" className="text-sm text-red-600 dark:text-red-400">
          {error}
        </p>
      )}

      {posts.length === 0 ? (
        <p className="text-sm text-black/60 dark:text-white/60">
          No planned posts yet — generate captions from a project&apos;s Repurpose page first.
        </p>
      ) : (
        <ul className="space-y-4">
          {posts.map((post) => {
            const scheduleDraft = scheduleDrafts[post.id] ?? { local: "", tz: post.timezone };
            const publishDraft = publishDrafts[post.id] ?? "";

            return (
              <li key={post.id} className="space-y-2 rounded border border-black/10 p-4 dark:border-white/10">
                <div className="flex items-center justify-between">
                  <span className="font-medium capitalize">{post.platform}</span>
                  <span className="rounded-full border border-black/20 px-2 py-0.5 text-xs dark:border-white/20">
                    {post.status}
                  </span>
                </div>
                <p className="text-sm text-black/80 dark:text-white/80">{post.caption}</p>
                <p className="text-xs text-black/60 dark:text-white/60">{formatLocal(post)}</p>

                {post.status === "published" ? (
                  <div className="flex items-center gap-2 text-xs">
                    {post.external_url && (
                      <a href={post.external_url} className="underline">
                        View live post
                      </a>
                    )}
                    <button
                      type="button"
                      disabled={busy !== null}
                      onClick={() => run(`unpublish-${post.id}`, () => api.post(`/api/posts/${post.id}/unpublish`))}
                      className="rounded border border-black/20 px-2 py-0.5 disabled:opacity-50 dark:border-white/20"
                    >
                      Undo publish
                    </button>
                  </div>
                ) : (
                  <div className="flex flex-wrap items-center gap-2">
                    <input
                      type="datetime-local"
                      value={scheduleDraft.local}
                      onChange={(e) =>
                        setScheduleDrafts((d) => ({
                          ...d,
                          [post.id]: { ...scheduleDraft, local: e.target.value },
                        }))
                      }
                      className="rounded border border-black/20 px-2 py-1 text-xs dark:border-white/20 dark:bg-transparent"
                    />
                    <button
                      type="button"
                      disabled={busy !== null || !scheduleDraft.local}
                      onClick={() =>
                        run(`schedule-${post.id}`, () =>
                          api.patch(`/api/posts/${post.id}`, {
                            scheduled_at_local: scheduleDraft.local,
                            timezone: scheduleDraft.tz,
                          }),
                        )
                      }
                      className="rounded border border-black/20 px-2 py-1 text-xs disabled:opacity-50 dark:border-white/20"
                    >
                      Schedule
                    </button>

                    <input
                      value={publishDraft}
                      onChange={(e) => setPublishDrafts((d) => ({ ...d, [post.id]: e.target.value }))}
                      placeholder="Live post URL"
                      className="min-w-48 rounded border border-black/20 px-2 py-1 text-xs dark:border-white/20 dark:bg-transparent"
                    />
                    <button
                      type="button"
                      disabled={busy !== null || !publishDraft}
                      onClick={() =>
                        run(`publish-${post.id}`, () =>
                          api.post(`/api/posts/${post.id}/publish`, { external_url: publishDraft }),
                        )
                      }
                      className="rounded bg-black px-2 py-1 text-xs font-medium text-white disabled:opacity-50 dark:bg-white dark:text-black"
                    >
                      Mark published
                    </button>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
