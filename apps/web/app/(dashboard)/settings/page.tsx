"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api/client";
import { createClient } from "@/lib/supabase/client";
import { BrandProfile, SubtitleStyle } from "@/lib/api/types";

/** FR-020 — creator voice profile and guardrails, injected into every
 * script, hook and caption prompt. */
export default function SettingsPage() {
  const [profile, setProfile] = useState<BrandProfile | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const [tone, setTone] = useState("");
  const [tradition, setTradition] = useState("");
  const [phrasesPrefer, setPhrasesPrefer] = useState("");
  const [phrasesAvoid, setPhrasesAvoid] = useState("");
  const [guardrails, setGuardrails] = useState("");
  const [avoidTopics, setAvoidTopics] = useState("");
  const [wpm, setWpm] = useState(150);
  const [timezone, setTimezone] = useState("Europe/London");
  const [englishVariant, setEnglishVariant] = useState("UK");
  const [xPremium, setXPremium] = useState(false);
  const [subtitleStyle, setSubtitleStyle] = useState<SubtitleStyle | null>(null);

  useEffect(() => {
    api
      .get<BrandProfile>("/api/brand-profile")
      .then((p) => {
        setProfile(p);
        setTone(p.tone ?? "");
        setTradition(p.tradition ?? "");
        setPhrasesPrefer(p.phrases_prefer.join("\n"));
        setPhrasesAvoid(p.phrases_avoid.join("\n"));
        setGuardrails(p.guardrails_json.join("\n"));
        setAvoidTopics(p.avoid_topics.join("\n"));
        setWpm(p.wpm);
        setTimezone(p.timezone);
        setEnglishVariant(p.english_variant);
        setXPremium(Boolean(p.platform_flags_json.x_premium));
        setSubtitleStyle(p.subtitle_style_json);
      })
      .catch((err: ApiError) => setError(err.message));
  }, []);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setSaved(false);
    setError(null);
    try {
      const updated = await api.patch<BrandProfile>("/api/brand-profile", {
        tone: tone || null,
        tradition: tradition || null,
        phrases_prefer: splitLines(phrasesPrefer),
        phrases_avoid: splitLines(phrasesAvoid),
        guardrails_json: splitLines(guardrails),
        avoid_topics: splitLines(avoidTopics),
        wpm,
        timezone,
        english_variant: englishVariant,
        platform_flags_json: { ...profile?.platform_flags_json, x_premium: xPremium },
        ...(subtitleStyle ? { subtitle_style_json: subtitleStyle } : {}),
      });
      setProfile(updated);
      setSaved(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't save your settings.");
    } finally {
      setSaving(false);
    }
  }

  if (error && !profile) {
    return (
      <p role="alert" className="text-sm text-red-600 dark:text-red-400">
        {error}
      </p>
    );
  }

  if (!profile) {
    return <p className="text-sm text-black/60 dark:text-white/60">Loading…</p>;
  }

  return (
    <>
    <form onSubmit={handleSave} className="max-w-xl space-y-6">
      <h1 className="text-xl font-semibold">Voice profile and guardrails</h1>
      <p className="text-sm text-black/60 dark:text-white/60">
        This is injected into every script, hook and caption the AI generates (FR-020).
      </p>

      <Field label="Tone">
        <input
          value={tone}
          onChange={(e) => setTone(e.target.value)}
          placeholder="e.g. warm, direct, encouraging"
          className="input"
        />
      </Field>

      <Field label="Theological tradition">
        <input value={tradition} onChange={(e) => setTradition(e.target.value)} className="input" />
      </Field>

      <Field label="Phrases to prefer (one per line)">
        <textarea
          value={phrasesPrefer}
          onChange={(e) => setPhrasesPrefer(e.target.value)}
          rows={3}
          className="input"
        />
      </Field>

      <Field label="Phrases to avoid (one per line)">
        <textarea
          value={phrasesAvoid}
          onChange={(e) => setPhrasesAvoid(e.target.value)}
          rows={3}
          className="input"
        />
      </Field>

      <Field label="Doctrinal guardrails (one per line)">
        <textarea
          value={guardrails}
          onChange={(e) => setGuardrails(e.target.value)}
          rows={3}
          className="input"
        />
      </Field>

      <Field label="Topics to avoid or handle with care (one per line)">
        <textarea
          value={avoidTopics}
          onChange={(e) => setAvoidTopics(e.target.value)}
          rows={3}
          className="input"
        />
      </Field>

      <Field label="Words per minute (used for duration estimates)">
        <input
          type="number"
          min={80}
          max={220}
          value={wpm}
          onChange={(e) => setWpm(Number(e.target.value))}
          className="input"
        />
      </Field>

      <Field label="Timezone (IANA)">
        <input value={timezone} onChange={(e) => setTimezone(e.target.value)} className="input" />
      </Field>

      <Field label="English variant">
        <select
          value={englishVariant}
          onChange={(e) => setEnglishVariant(e.target.value)}
          className="input"
        >
          <option value="UK">UK</option>
          <option value="US">US</option>
        </select>
      </Field>

      <div className="space-y-1">
        <label className="flex items-center gap-2 text-sm font-medium">
          <input type="checkbox" checked={xPremium} onChange={(e) => setXPremium(e.target.checked)} />
          X Premium account (raises the caption and video-length limits — FR-026)
        </label>
      </div>

      {subtitleStyle && <SubtitleStyleFields value={subtitleStyle} onChange={setSubtitleStyle} />}

      {error && (
        <p role="alert" className="text-sm text-red-600 dark:text-red-400">
          {error}
        </p>
      )}
      {saved && <p className="text-sm text-green-700 dark:text-green-400">Saved.</p>}

      <button
        type="submit"
        disabled={saving}
        className="rounded bg-black px-3 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-black"
      >
        {saving ? "Saving…" : "Save"}
      </button>
    </form>
    <DataManagement />
    </>
  );
}

function DataManagement() {
  const router = useRouter();
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleExport() {
    setBusy("export");
    setError(null);
    try {
      const data = await api.post("/api/export");
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "amplify-studio-export.json";
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't export your data.");
    } finally {
      setBusy(null);
    }
  }

  async function handleDeleteWorkspace() {
    if (
      !window.confirm(
        "This permanently deletes your entire workspace — every project, script, video, post and metric. This cannot be undone. Continue?",
      )
    ) {
      return;
    }
    setBusy("delete");
    setError(null);
    try {
      await api.del("/api/workspace");
      const supabase = createClient();
      await supabase.auth.signOut();
      router.push("/login");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't delete your workspace.");
      setBusy(null);
    }
  }

  return (
    <section className="mt-10 max-w-xl space-y-3 border-t border-black/10 pt-6 dark:border-white/10">
      <h2 className="text-lg font-semibold">Data export and deletion</h2>
      <p className="text-sm text-black/60 dark:text-white/60">FR-030.</p>

      {error && (
        <p role="alert" className="text-sm text-red-600 dark:text-red-400">
          {error}
        </p>
      )}

      <div className="flex gap-2">
        <button
          type="button"
          disabled={busy !== null}
          onClick={handleExport}
          className="rounded border border-black/20 px-3 py-2 text-sm font-medium disabled:opacity-50 dark:border-white/20"
        >
          {busy === "export" ? "Exporting…" : "Export all my data"}
        </button>
        <button
          type="button"
          disabled={busy !== null}
          onClick={handleDeleteWorkspace}
          className="rounded border border-red-600 px-3 py-2 text-sm font-medium text-red-600 disabled:opacity-50 dark:border-red-400 dark:text-red-400"
        >
          {busy === "delete" ? "Deleting…" : "Delete my entire workspace"}
        </button>
      </div>
    </section>
  );
}

/** FR-009 — style for burned-in captions. Defaults (32 characters x 2 lines,
 * clear of the bottom 20% and right 12%) come from the API; the server
 * rejects a font too large to fit a full line inside the safe zone. */
function SubtitleStyleFields({
  value,
  onChange,
}: {
  value: SubtitleStyle;
  onChange: (next: SubtitleStyle) => void;
}) {
  function set<K extends keyof SubtitleStyle>(key: K, next: SubtitleStyle[K]) {
    onChange({ ...value, [key]: next });
  }

  return (
    <fieldset className="space-y-4 border-t border-black/10 pt-6 dark:border-white/10">
      <legend className="text-lg font-semibold">Burned-in captions</legend>
      <p className="text-sm text-black/60 dark:text-white/60">
        Used when rendering a video with captions in Video Studio (FR-009).
      </p>

      <div className="flex flex-wrap items-start gap-6">
        <div className="grid min-w-64 flex-1 grid-cols-2 gap-3">
          <Field label="Font">
            <input
              value={value.font_family}
              onChange={(e) => set("font_family", e.target.value)}
              className="input"
            />
          </Field>
          <Field label="Font size (px at 1080×1920)">
            <input
              type="number"
              min={24}
              max={120}
              value={value.font_size}
              onChange={(e) => set("font_size", Number(e.target.value))}
              className="input"
            />
          </Field>
          <Field label="Text colour">
            <input
              type="color"
              aria-label="Text colour"
              value={value.text_colour}
              onChange={(e) => set("text_colour", e.target.value.toUpperCase())}
              className="h-9 w-full"
            />
          </Field>
          <Field label="Box colour">
            <input
              type="color"
              aria-label="Box colour"
              value={value.background_colour}
              disabled={!value.background_box}
              onChange={(e) => set("background_colour", e.target.value.toUpperCase())}
              className="h-9 w-full disabled:opacity-50"
            />
          </Field>
          <Field label="Box opacity (%)">
            <input
              type="number"
              min={0}
              max={100}
              value={Math.round(value.background_opacity * 100)}
              disabled={!value.background_box}
              onChange={(e) => set("background_opacity", Number(e.target.value) / 100)}
              className="input"
            />
          </Field>
          <Field label="Characters per line">
            <input
              type="number"
              min={10}
              max={60}
              value={value.max_chars_per_line}
              onChange={(e) => set("max_chars_per_line", Number(e.target.value))}
              className="input"
            />
          </Field>
          <Field label="Lines per caption">
            <input
              type="number"
              min={1}
              max={3}
              value={value.max_lines}
              onChange={(e) => set("max_lines", Number(e.target.value))}
              className="input"
            />
          </Field>
          <Field label="Keep clear of bottom (%)">
            <input
              type="number"
              min={0}
              max={50}
              value={value.safe_zone_bottom_pct}
              onChange={(e) => set("safe_zone_bottom_pct", Number(e.target.value))}
              className="input"
            />
          </Field>
          <Field label="Keep clear of right (%)">
            <input
              type="number"
              min={0}
              max={40}
              value={value.safe_zone_right_pct}
              onChange={(e) => set("safe_zone_right_pct", Number(e.target.value))}
              className="input"
            />
          </Field>
          <div className="col-span-2 flex flex-wrap gap-4">
            <label className="flex items-center gap-2 text-sm font-medium">
              <input
                type="checkbox"
                checked={value.background_box}
                onChange={(e) => set("background_box", e.target.checked)}
              />
              Background box
            </label>
            <label className="flex items-center gap-2 text-sm font-medium">
              <input type="checkbox" checked={value.bold} onChange={(e) => set("bold", e.target.checked)} />
              Bold
            </label>
          </div>
        </div>
        <SafeZonePreview style={value} />
      </div>
    </fieldset>
  );
}

const PREVIEW_WIDTH = 135; // px — the render frame is 1080 wide, so 1/8 scale

function SafeZonePreview({ style }: { style: SubtitleStyle }) {
  const scale = PREVIEW_WIDTH / 1080;
  const sample = "Grace is not a reward for the faithful".slice(0, style.max_chars_per_line);
  const boxAlpha = Math.round(style.background_opacity * 255)
    .toString(16)
    .padStart(2, "0");
  return (
    <figure className="space-y-1">
      <div
        aria-label="Caption safe-zone preview"
        className="relative overflow-hidden rounded bg-neutral-700"
        style={{ width: PREVIEW_WIDTH, aspectRatio: "9 / 16" }}
      >
        <div
          className="absolute inset-x-0 bottom-0 bg-red-500/30"
          style={{ height: `${style.safe_zone_bottom_pct}%` }}
        />
        <div
          className="absolute inset-y-0 right-0 bg-red-500/30"
          style={{ width: `${style.safe_zone_right_pct}%` }}
        />
        <div
          className="absolute flex justify-center"
          style={{
            left: `${style.safe_zone_left_pct}%`,
            right: `${style.safe_zone_right_pct}%`,
            bottom: `${style.safe_zone_bottom_pct}%`,
          }}
        >
          <span
            className="px-0.5 text-center leading-tight"
            style={{
              fontFamily: style.font_family,
              fontSize: Math.max(style.font_size * scale, 4),
              fontWeight: style.bold ? 700 : 400,
              color: style.text_colour,
              background: style.background_box ? `${style.background_colour}${boxAlpha}` : "transparent",
            }}
          >
            {sample}
          </span>
        </div>
      </div>
      <figcaption className="text-xs text-black/60 dark:text-white/60" style={{ width: PREVIEW_WIDTH }}>
        Shaded areas are kept clear of captions for the platforms&apos; own buttons and text.
      </figcaption>
    </figure>
  );
}

function splitLines(value: string): string[] {
  return value
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <label className="block text-sm font-medium">{label}</label>
      {children}
    </div>
  );
}
