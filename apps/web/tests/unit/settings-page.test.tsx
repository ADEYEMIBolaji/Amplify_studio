import { act, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import SettingsPage from "@/app/(dashboard)/settings/page";
import { api } from "@/lib/api/client";

vi.mock("@/lib/api/client", () => ({
  api: { get: vi.fn(), patch: vi.fn(), post: vi.fn(), del: vi.fn() },
  ApiError: class ApiError extends Error {},
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
}));

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({ auth: { signOut: vi.fn() } }),
}));

const baseProfile = {
  id: "p1",
  workspace_id: "w1",
  tone: "warm",
  voice_samples_json: [],
  phrases_prefer: ["grace"],
  phrases_avoid: ["just"],
  tradition: "Baptist",
  guardrails_json: [],
  avoid_topics: [],
  translation: "WEB",
  english_variant: "UK",
  wpm: 150,
  timezone: "Europe/London",
  platform_flags_json: {},
  subtitle_style_json: {
    font_family: "DejaVu Sans",
    font_size: 48,
    bold: true,
    text_colour: "#FFFFFF",
    background_box: true,
    background_colour: "#000000",
    background_opacity: 0.6,
    max_chars_per_line: 32,
    max_lines: 2,
    safe_zone_bottom_pct: 20,
    safe_zone_right_pct: 12,
    safe_zone_left_pct: 6,
  },
  version_no: 1,
};

describe("SettingsPage", () => {
  it("loads the brand profile into the form fields", async () => {
    vi.mocked(api.get).mockResolvedValue(baseProfile);

    render(<SettingsPage />);

    await waitFor(() => expect(screen.getByDisplayValue("warm")).toBeInTheDocument());
    expect(screen.getByDisplayValue("Baptist")).toBeInTheDocument();
    expect(screen.getByDisplayValue("150")).toBeInTheDocument();
  });

  it("saves edits via PATCH /api/brand-profile", async () => {
    vi.mocked(api.get).mockResolvedValue(baseProfile);
    vi.mocked(api.patch).mockResolvedValue({ ...baseProfile, tone: "bold", version_no: 2 });

    render(<SettingsPage />);
    await waitFor(() => expect(screen.getByDisplayValue("warm")).toBeInTheDocument());

    await act(async () => {
      screen.getByRole("button", { name: /save/i }).click();
    });

    expect(api.patch).toHaveBeenCalledWith(
      "/api/brand-profile",
      expect.objectContaining({ tone: "warm" }),
    );
  });
});
