"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { api, ApiError } from "@/lib/api/client";
import {
  HookVariant,
  Project,
  SCRIPT_SECTIONS,
  ScriptSection,
  ScriptureReference,
  ScriptVersion,
} from "@/lib/api/types";

const SECTION_LABELS: Record<ScriptSection, string> = {
  hook: "Hook",
  biblical_context: "Biblical context",
  main_teaching: "Main teaching",
  practical_application: "Practical application",
  closing_cta: "Closing CTA",
};

export default function ProjectDetailPage() {
  const params = useParams<{ id: string }>();
  const projectId = params.id;

  const [project, setProject] = useState<Project | null>(null);
  const [hooks, setHooks] = useState<HookVariant[] | null>(null);
  const [versions, setVersions] = useState<ScriptVersion[] | null>(null);
  const [references, setReferences] = useState<ScriptureReference[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    try {
      const [p, h, v, r] = await Promise.all([
        api.get<Project>(`/api/projects/${projectId}`),
        api.get<HookVariant[]>(`/api/projects/${projectId}/hooks`),
        api.get<ScriptVersion[]>(`/api/projects/${projectId}/scripts`),
        api.get<ScriptureReference[]>(`/api/projects/${projectId}/references`),
      ]);
      setProject(p);
      setHooks(h);
      setVersions(v);
      setReferences(r);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't load this project.");
    }
  }, [projectId]);

  useEffect(() => {
    // Fetch-on-mount: `load` sets state once data arrives, not synchronously here.
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

  if (error && !project) {
    return (
      <p role="alert" className="text-sm text-red-600 dark:text-red-400">
        {error}
      </p>
    );
  }

  if (!project || !hooks || !versions || !references) {
    return <p className="text-sm text-black/60 dark:text-white/60">Loading…</p>;
  }

  const latest = versions[0] ?? null;

  return (
    <div className="space-y-10">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold">{project.title}</h1>
          <p className="text-sm text-black/60 dark:text-white/60">{project.topic}</p>
        </div>
        <span className="rounded-full border border-black/20 px-2 py-0.5 text-xs dark:border-white/20">
          {project.status.replace("_", " ")}
        </span>
      </div>

      {error && (
        <p role="alert" className="text-sm text-red-600 dark:text-red-400">
          {error}
        </p>
      )}

      <div className="flex gap-2">
        {latest && (
          <Link
            href={`/projects/${projectId}/teleprompter`}
            className="inline-block rounded bg-black px-3 py-2 text-sm font-medium text-white dark:bg-white dark:text-black"
          >
            Open teleprompter
          </Link>
        )}
        <Link
          href={`/projects/${projectId}/video`}
          className="inline-block rounded border border-black/20 px-3 py-2 text-sm font-medium dark:border-white/20"
        >
          Video Studio
        </Link>
      </div>

      {/* Hooks — FR-022 */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="font-medium">Hook variants</h2>
          <button
            type="button"
            disabled={busy !== null}
            onClick={() => run("hooks", () => api.post(`/api/projects/${projectId}/hooks`))}
            className="rounded border border-black/20 px-2 py-1 text-xs disabled:opacity-50 dark:border-white/20"
          >
            {busy === "hooks" ? "Generating…" : "Generate hooks"}
          </button>
        </div>
        {hooks.length === 0 ? (
          <p className="text-sm text-black/60 dark:text-white/60">No hook variants yet.</p>
        ) : (
          <ul className="space-y-2">
            {hooks.map((hook) => (
              <li
                key={hook.id}
                className={`flex items-center justify-between rounded border p-3 text-sm ${
                  hook.selected
                    ? "border-black bg-black/5 dark:border-white dark:bg-white/10"
                    : "border-black/10 dark:border-white/10"
                }`}
              >
                <div>
                  <p>{hook.text}</p>
                  <p className="text-xs text-black/60 dark:text-white/60">{hook.hook_type}</p>
                </div>
                {!hook.selected && (
                  <button
                    type="button"
                    disabled={busy !== null}
                    onClick={() =>
                      run(`select-hook-${hook.id}`, () =>
                        api.patch(`/api/hooks/${hook.id}`, { selected: true }),
                      )
                    }
                    className="shrink-0 rounded border border-black/20 px-2 py-1 text-xs disabled:opacity-50 dark:border-white/20"
                  >
                    Use this
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Script — FR-004, FR-005 */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="font-medium">Script</h2>
          <div className="flex gap-2">
            <button
              type="button"
              disabled={busy !== null}
              onClick={() => run("outline", () => api.post(`/api/projects/${projectId}/outline`))}
              className="rounded border border-black/20 px-2 py-1 text-xs disabled:opacity-50 dark:border-white/20"
            >
              {busy === "outline" ? "Generating…" : latest ? "Regenerate full script" : "Generate script"}
            </button>
            {latest && !latest.approved && (
              <button
                type="button"
                disabled={busy !== null}
                onClick={() => run("approve", () => api.post(`/api/scripts/${latest.id}/approve`))}
                className="rounded bg-black px-2 py-1 text-xs font-medium text-white disabled:opacity-50 dark:bg-white dark:text-black"
              >
                Approve this version
              </button>
            )}
          </div>
        </div>

        {!latest ? (
          <p className="text-sm text-black/60 dark:text-white/60">No script yet.</p>
        ) : (
          <div className="space-y-4">
            <p className="text-xs text-black/60 dark:text-white/60">
              v{latest.version_no} · {latest.source} · {latest.word_count} words · ~
              {Math.round(latest.estimated_duration_seconds)}s{latest.approved ? " · approved" : ""}
            </p>

            {SCRIPT_SECTIONS.map((section) => {
              const content = latest.sections[section];
              const draftKey = `${latest.id}:${section}`;
              const draftValue = drafts[draftKey] ?? content.text;
              return (
                <div key={section} className="space-y-1">
                  <div className="flex items-center justify-between">
                    <label className="text-sm font-medium">{SECTION_LABELS[section]}</label>
                    <span className="text-xs text-black/60 dark:text-white/60">{content.source}</span>
                  </div>
                  <textarea
                    value={draftValue}
                    onChange={(e) => setDrafts((d) => ({ ...d, [draftKey]: e.target.value }))}
                    rows={3}
                    className="w-full rounded border border-black/20 px-3 py-2 text-sm dark:border-white/20 dark:bg-transparent"
                  />
                  <div className="flex gap-2">
                    <button
                      type="button"
                      disabled={busy !== null || draftValue === content.text}
                      onClick={() =>
                        run(`save-${section}`, () =>
                          api.patch(`/api/scripts/${latest.id}`, { sections: { [section]: draftValue } }),
                        )
                      }
                      className="rounded border border-black/20 px-2 py-1 text-xs disabled:opacity-50 dark:border-white/20"
                    >
                      Save edit
                    </button>
                    <button
                      type="button"
                      disabled={busy !== null}
                      onClick={() =>
                        run(`regen-${section}`, async () => {
                          try {
                            await api.post(`/api/scripts/${latest.id}/regenerate-section`, { section });
                          } catch (err) {
                            if (
                              err instanceof ApiError &&
                              err.code === "manual_edit_would_be_overwritten" &&
                              window.confirm(
                                "This section was manually edited. Let AI overwrite it anyway?",
                              )
                            ) {
                              await api.post(`/api/scripts/${latest.id}/regenerate-section`, {
                                section,
                                confirm: true,
                              });
                              return;
                            }
                            throw err;
                          }
                        })
                      }
                      className="rounded border border-black/20 px-2 py-1 text-xs disabled:opacity-50 dark:border-white/20"
                    >
                      Regenerate
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {versions.length > 1 && (
          <details className="text-sm">
            <summary className="cursor-pointer text-black/60 dark:text-white/60">
              Version history ({versions.length})
            </summary>
            <ul className="mt-2 space-y-1">
              {versions.map((v) => (
                <li key={v.id} className="flex items-center justify-between">
                  <span>
                    v{v.version_no} · {v.source}
                    {v.approved ? " · approved" : ""}
                  </span>
                  {v.id !== latest?.id && (
                    <button
                      type="button"
                      disabled={busy !== null}
                      onClick={() => run(`restore-${v.id}`, () => api.post(`/api/scripts/${v.id}/restore`))}
                      className="rounded border border-black/20 px-2 py-0.5 text-xs disabled:opacity-50 dark:border-white/20"
                    >
                      Restore
                    </button>
                  )}
                </li>
              ))}
            </ul>
          </details>
        )}
      </section>

      {/* Scripture references — FR-003 */}
      <section className="space-y-3">
        <h2 className="font-medium">Scripture references</h2>
        {references.length === 0 ? (
          <p className="text-sm text-black/60 dark:text-white/60">
            None yet — references appear here once a script cites them.
          </p>
        ) : (
          <ul className="space-y-2">
            {references.map((ref) => (
              <li key={ref.id} className="rounded border border-black/10 p-3 text-sm dark:border-white/10">
                <div className="flex items-center justify-between">
                  <span className="font-medium">
                    {ref.reference} ({ref.translation})
                  </span>
                  {ref.verified_at ? (
                    <span className="text-xs text-green-700 dark:text-green-400">Verified</span>
                  ) : (
                    <button
                      type="button"
                      disabled={busy !== null}
                      onClick={() =>
                        run(`verify-${ref.id}`, () => api.post(`/api/references/${ref.id}/verify`))
                      }
                      className="rounded border border-black/20 px-2 py-0.5 text-xs disabled:opacity-50 dark:border-white/20"
                    >
                      Mark verified
                    </button>
                  )}
                </div>
                <p className="mt-1 text-xs text-black/60 dark:text-white/60">
                  Source: {ref.source}. Paste your own text below if this translation isn&apos;t
                  available locally.
                </p>
                <textarea
                  defaultValue={ref.pasted_text ?? ""}
                  rows={2}
                  placeholder="Paste verse text here (Owner-supplied)"
                  onBlur={(e) => {
                    if (e.target.value !== (ref.pasted_text ?? "")) {
                      run(`paste-${ref.id}`, () =>
                        api.patch(`/api/references/${ref.id}`, { pasted_text: e.target.value }),
                      );
                    }
                  }}
                  className="mt-2 w-full rounded border border-black/20 px-2 py-1 text-xs dark:border-white/20 dark:bg-transparent"
                />
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
