"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api/client";
import { ExpandVersesResponse, SCRIPT_SECTIONS, ScriptVersion } from "@/lib/api/types";

/** FR-006 Teleprompter — Prompter-only mode (second device). In-app Record
 * mode (FR-024) is a Week 4 stretch (D-01); this screen only displays text. */
export default function TeleprompterPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const projectId = params.id;

  const [text, setText] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [fontSize, setFontSize] = useState(32);
  const [speed, setSpeed] = useState(40); // px/sec
  const [mirrored, setMirrored] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [countdown, setCountdown] = useState<number | null>(null);
  const [wakeLockSupported, setWakeLockSupported] = useState(true);

  const scrollRef = useRef<HTMLDivElement>(null);
  const wakeLockRef = useRef<WakeLockSentinel | null>(null);
  const rafRef = useRef<number | null>(null);
  const lastTsRef = useRef<number | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const versions = await api.get<ScriptVersion[]>(`/api/projects/${projectId}/scripts`);
        const target = versions.find((v) => v.approved) ?? versions[0];
        if (!target) {
          if (!cancelled) setError("This project has no script yet.");
          return;
        }
        const expanded = await api.post<ExpandVersesResponse>(`/api/scripts/${target.id}/expand-verses`);
        if (cancelled) return;
        const combined = SCRIPT_SECTIONS.map((section) => expanded.sections[section]).join("\n\n");
        setText(combined);
      } catch (err) {
        if (!cancelled) setError(err instanceof ApiError ? err.message : "Couldn't load the script.");
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  const releaseWakeLock = useCallback(() => {
    wakeLockRef.current?.release().catch(() => {});
    wakeLockRef.current = null;
  }, []);

  const requestWakeLock = useCallback(async () => {
    if (!("wakeLock" in navigator)) {
      setWakeLockSupported(false);
      return;
    }
    try {
      wakeLockRef.current = await navigator.wakeLock.request("screen");
    } catch {
      setWakeLockSupported(false);
    }
  }, []);

  useEffect(() => {
    // Syncing the hardware wake lock to `playing`; setState only fires if the
    // browser rejects the request (unsupported/denied), which is a legitimate
    // external-system outcome, not a render-cascade risk.
    if (playing) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      requestWakeLock();
    } else {
      releaseWakeLock();
    }
    return releaseWakeLock;
  }, [playing, requestWakeLock, releaseWakeLock]);

  // Auto-scroll loop while playing.
  useEffect(() => {
    if (!playing) {
      lastTsRef.current = null;
      return;
    }

    function tick(ts: number) {
      const el = scrollRef.current;
      if (el) {
        if (lastTsRef.current !== null) {
          const deltaSeconds = (ts - lastTsRef.current) / 1000;
          el.scrollTop += speed * deltaSeconds;
        }
        lastTsRef.current = ts;
      }
      rafRef.current = requestAnimationFrame(tick);
    }

    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [playing, speed]);

  function startCountdown() {
    setCountdown(3);
  }

  useEffect(() => {
    if (countdown === null) return;
    // Each tick is driven by the setTimeout callback, not the effect body
    // itself, so the countdown -> "Go" -> playing handoff happens in a
    // callback rather than synchronously during the effect.
    const timer = setTimeout(() => {
      setCountdown((current) => {
        const value = current ?? 1;
        if (value <= 0) {
          setPlaying(true);
          return null;
        }
        return value - 1;
      });
    }, 1000);
    return () => clearTimeout(timer);
  }, [countdown]);

  function handleTapToPauseResume() {
    if (countdown !== null) return;
    setPlaying((p) => !p);
  }

  if (error) {
    return (
      <div className="p-6">
        <p role="alert" className="text-sm text-red-600 dark:text-red-400">
          {error}
        </p>
        <button onClick={() => router.back()} className="mt-4 text-sm underline">
          Back
        </button>
      </div>
    );
  }

  if (text === null) {
    return <p className="p-6 text-sm text-black/60 dark:text-white/60">Loading…</p>;
  }

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-black text-white">
      <div className="flex flex-wrap items-center gap-3 border-b border-white/20 p-3 text-sm">
        <button onClick={() => router.back()} className="underline">
          Exit
        </button>
        <label className="flex items-center gap-1">
          Font
          <input
            type="range"
            min={20}
            max={64}
            value={fontSize}
            onChange={(e) => setFontSize(Number(e.target.value))}
          />
        </label>
        <label className="flex items-center gap-1">
          Speed
          <input
            type="range"
            min={10}
            max={150}
            value={speed}
            onChange={(e) => setSpeed(Number(e.target.value))}
          />
        </label>
        <label className="flex items-center gap-1">
          <input type="checkbox" checked={mirrored} onChange={(e) => setMirrored(e.target.checked)} />
          Mirror
        </label>
        {countdown === null && (
          <button
            onClick={() => (playing ? setPlaying(false) : startCountdown())}
            className="rounded bg-white px-2 py-1 text-xs font-medium text-black"
          >
            {playing ? "Pause" : "Start"}
          </button>
        )}
        {!wakeLockSupported && (
          <span className="text-xs text-yellow-400">
            Screen wake lock isn&apos;t supported here — adjust your device&apos;s sleep setting.
          </span>
        )}
      </div>

      <div
        ref={scrollRef}
        onClick={handleTapToPauseResume}
        className="flex-1 overflow-y-auto px-6 py-12"
        style={{ transform: mirrored ? "scaleX(-1)" : undefined }}
      >
        <p style={{ fontSize }} className="mx-auto max-w-2xl whitespace-pre-wrap leading-relaxed">
          {text}
        </p>
        <div className="h-[60vh]" />
      </div>

      {countdown !== null && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/80 text-8xl font-bold">
          {countdown === 0 ? "Go" : countdown}
        </div>
      )}
    </div>
  );
}
