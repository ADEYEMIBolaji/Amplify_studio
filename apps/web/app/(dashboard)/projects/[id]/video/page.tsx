"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { api, ApiError } from "@/lib/api/client";
import { MediaAsset, MediaUploadSession, RenderFitMode, Transcript } from "@/lib/api/types";
import { isVertical916 } from "@/lib/media";

const CHUNK_SIZE = 5 * 1024 * 1024; // 5 MB

/** FR-007/FR-008/FR-009 (Video Studio): upload, transcribe, edit subtitles,
 * then export a captioned 1080×1920 render and/or an SRT. */
export default function VideoStudioPage() {
  const params = useParams<{ id: string }>();
  const projectId = params.id;

  const [assets, setAssets] = useState<MediaAsset[] | null>(null);
  const [transcript, setTranscript] = useState<Transcript | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [segmentDrafts, setSegmentDrafts] = useState<Transcript["segments"] | null>(null);

  const sourceAsset = assets?.find((a) => a.kind === "source") ?? null;
  const srtAsset = assets?.find((a) => a.kind === "srt") ?? null;
  // Earlier renders are kept (they may be attached to posts); show the newest.
  const latestRender =
    assets
      ?.filter((a) => a.kind === "render")
      .sort((a, b) => (b.created_at ?? "").localeCompare(a.created_at ?? ""))[0] ?? null;
  const needsFitChoice = sourceAsset !== null && !isVertical916(sourceAsset.width, sourceAsset.height);
  const [fitMode, setFitMode] = useState<RenderFitMode | null>(null);

  const loadAssets = useCallback(async () => {
    try {
      setAssets(await api.get<MediaAsset[]>(`/api/projects/${projectId}/media`));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't load media.");
    }
  }, [projectId]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadAssets();
  }, [loadAssets]);

  useEffect(() => {
    if (!sourceAsset || sourceAsset.status !== "ready") {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setTranscript(null);
      return;
    }
    api
      .get<Transcript>(`/api/media/${sourceAsset.id}/transcript`)
      .then((t) => {
        setTranscript(t);
        setSegmentDrafts(t.segments);
      })
      .catch(() => setTranscript(null));
  }, [sourceAsset]);

  async function handleFileSelected(file: File) {
    setError(null);
    setUploadProgress(0);
    try {
      const session = await api.post<MediaUploadSession>("/api/media/uploads", {
        project_id: projectId,
        filename: file.name,
        content_type: file.type || "video/mp4",
        total_size: file.size,
        chunk_size: CHUNK_SIZE,
      });

      for (let i = 0; i < session.total_chunks; i++) {
        const start = i * session.chunk_size;
        const end = Math.min(start + session.chunk_size, file.size);
        const chunk = file.slice(start, end);
        await api.putRaw(`/api/media/uploads/${session.id}/chunks/${i}`, chunk);
        setUploadProgress(Math.round(((i + 1) / session.total_chunks) * 100));
      }

      await api.post(`/api/media/uploads/${session.id}/complete`);
      setUploadProgress(null);
      await loadAssets();
    } catch (err) {
      setUploadProgress(null);
      setError(err instanceof ApiError ? err.message : "Upload failed.");
    }
  }

  async function run(action: string, fn: () => Promise<unknown>) {
    setBusy(action);
    setError(null);
    try {
      await fn();
      await loadAssets();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setBusy(null);
    }
  }

  if (error && assets === null) {
    return (
      <p role="alert" className="text-sm text-red-600 dark:text-red-400">
        {error}
      </p>
    );
  }

  if (assets === null) {
    return <p className="text-sm text-black/60 dark:text-white/60">Loading…</p>;
  }

  return (
    <div className="space-y-8">
      <h1 className="text-xl font-semibold">Video Studio</h1>

      {error && (
        <p role="alert" className="text-sm text-red-600 dark:text-red-400">
          {error}
        </p>
      )}

      <section className="space-y-3">
        <h2 className="font-medium">Upload</h2>
        <input
          ref={fileInputRef}
          type="file"
          accept="video/mp4,video/quicktime"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) handleFileSelected(file);
          }}
          className="text-sm"
        />
        {uploadProgress !== null && (
          <p className="text-sm text-black/60 dark:text-white/60">Uploading… {uploadProgress}%</p>
        )}
      </section>

      {sourceAsset && (
        <section className="space-y-3">
          <h2 className="font-medium">Source video</h2>
          <p className="text-sm text-black/60 dark:text-white/60">
            Status: {sourceAsset.status}
            {sourceAsset.duration_seconds ? ` · ${Math.round(sourceAsset.duration_seconds)}s` : ""}
            {sourceAsset.width ? ` · ${sourceAsset.width}×${sourceAsset.height}` : ""}
          </p>
          {sourceAsset.metadata_json.degraded === true && (
            <p className="text-xs text-yellow-700 dark:text-yellow-400">
              Processed without real FFmpeg normalisation in this environment — the file was
              stored as-is.
            </p>
          )}

          {sourceAsset.status === "ready" && !transcript && (
            <button
              type="button"
              disabled={busy !== null}
              onClick={() => run("transcribe", () => api.post(`/api/media/${sourceAsset.id}/transcribe`))}
              className="rounded border border-black/20 px-2 py-1 text-xs disabled:opacity-50 dark:border-white/20"
            >
              {busy === "transcribe" ? "Transcribing…" : "Transcribe"}
            </button>
          )}
        </section>
      )}

      {transcript && segmentDrafts && (
        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="font-medium">Subtitles</h2>
            {transcript.reviewed_at ? (
              <span className="text-xs text-green-700 dark:text-green-400">Reviewed</span>
            ) : (
              <button
                type="button"
                disabled={busy !== null}
                onClick={() =>
                  run("review", () => api.post(`/api/transcripts/${transcript.id}/review`))
                }
                className="rounded border border-black/20 px-2 py-1 text-xs disabled:opacity-50 dark:border-white/20"
              >
                Mark reviewed
              </button>
            )}
          </div>

          <ul className="space-y-2">
            {segmentDrafts.map((segment, i) => (
              <li key={i} className="flex gap-2 rounded border border-black/10 p-2 text-sm dark:border-white/10">
                <input
                  type="number"
                  step="0.1"
                  value={segment.start}
                  onChange={(e) => {
                    const next = [...segmentDrafts];
                    next[i] = { ...next[i], start: Number(e.target.value) };
                    setSegmentDrafts(next);
                  }}
                  className="w-16 rounded border border-black/20 px-1 text-xs dark:border-white/20 dark:bg-transparent"
                />
                <input
                  type="number"
                  step="0.1"
                  value={segment.end}
                  onChange={(e) => {
                    const next = [...segmentDrafts];
                    next[i] = { ...next[i], end: Number(e.target.value) };
                    setSegmentDrafts(next);
                  }}
                  className="w-16 rounded border border-black/20 px-1 text-xs dark:border-white/20 dark:bg-transparent"
                />
                <textarea
                  value={segment.text}
                  onChange={(e) => {
                    const next = [...segmentDrafts];
                    next[i] = { ...next[i], text: e.target.value };
                    setSegmentDrafts(next);
                  }}
                  rows={1}
                  className="flex-1 rounded border border-black/20 px-2 py-1 text-xs dark:border-white/20 dark:bg-transparent"
                />
              </li>
            ))}
          </ul>
          <button
            type="button"
            disabled={busy !== null}
            onClick={() =>
              run("save-segments", () =>
                api.patch(`/api/transcripts/${transcript.id}`, { segments: segmentDrafts }),
              )
            }
            className="rounded border border-black/20 px-2 py-1 text-xs disabled:opacity-50 dark:border-white/20"
          >
            Save subtitle edits
          </button>
        </section>
      )}

      {sourceAsset?.status === "ready" && transcript && (
        <section className="space-y-3">
          <h2 className="font-medium">Export</h2>

          <div className="space-y-2 rounded border border-black/10 p-3 dark:border-white/10">
            <h3 className="text-sm font-medium">Captioned video (1080×1920 MP4)</h3>
            {!transcript.reviewed_at ? (
              <p className="text-xs text-black/60 dark:text-white/60">
                Mark the subtitles reviewed first — burned-in captions can&apos;t be edited after
                rendering.
              </p>
            ) : (
              <>
                {needsFitChoice && (
                  <fieldset className="space-y-1 text-sm">
                    <legend className="text-xs text-black/60 dark:text-white/60">
                      This video is {sourceAsset.width}×{sourceAsset.height}, not 9:16. Choose how to
                      fit it:
                    </legend>
                    <label className="mr-4 inline-flex items-center gap-1">
                      <input
                        type="radio"
                        name="fit-mode"
                        checked={fitMode === "crop"}
                        onChange={() => setFitMode("crop")}
                      />
                      Centre-crop
                    </label>
                    <label className="inline-flex items-center gap-1">
                      <input
                        type="radio"
                        name="fit-mode"
                        checked={fitMode === "pad"}
                        onChange={() => setFitMode("pad")}
                      />
                      Blurred-background pad
                    </label>
                  </fieldset>
                )}
                <p className="text-xs text-black/60 dark:text-white/60">
                  Caption style and safe zone come from Settings. Audio is normalised to about −14 LUFS.
                </p>
                <button
                  type="button"
                  disabled={busy !== null || (needsFitChoice && fitMode === null)}
                  onClick={() =>
                    run("render", () =>
                      api.post(`/api/media/${sourceAsset.id}/render`, {
                        fit_mode: needsFitChoice ? fitMode : null,
                      }),
                    )
                  }
                  className="rounded border border-black/20 px-2 py-1 text-xs disabled:opacity-50 dark:border-white/20"
                >
                  {busy === "render" ? "Rendering…" : latestRender ? "Render again" : "Render with captions"}
                </button>
              </>
            )}

            {latestRender && (
              <div className="space-y-1 text-sm">
                {latestRender.status === "ready" && latestRender.download_url && (
                  <a href={latestRender.download_url} className="underline">
                    Download captioned MP4
                  </a>
                )}
                {latestRender.status === "processing" && (
                  <p className="text-black/60 dark:text-white/60">Rendering…</p>
                )}
                {latestRender.status === "failed" && (
                  <p role="alert" className="text-red-600 dark:text-red-400">
                    The last render failed. Try again; if it keeps failing, use the SRT instead.
                  </p>
                )}
                {latestRender.metadata_json.degraded === true && (
                  <p className="text-xs text-yellow-700 dark:text-yellow-400">
                    Captions were not burned in: this environment has no FFmpeg, so this file is your
                    source video unchanged. Render where FFmpeg is installed (the worker container), or
                    upload the SRT alongside the video for now.
                  </p>
                )}
              </div>
            )}
          </div>

          {srtAsset?.download_url ? (
            <a href={srtAsset.download_url} className="text-sm underline">
              Download SRT
            </a>
          ) : (
            <button
              type="button"
              disabled={busy !== null}
              onClick={() => run("export-srt", () => api.post(`/api/media/${sourceAsset.id}/export-srt`))}
              className="rounded border border-black/20 px-2 py-1 text-xs disabled:opacity-50 dark:border-white/20"
            >
              {busy === "export-srt" ? "Exporting…" : "Export SRT"}
            </button>
          )}
        </section>
      )}
    </div>
  );
}
