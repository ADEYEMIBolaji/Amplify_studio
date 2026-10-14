import { act, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import SettingsPage from "@/app/(dashboard)/settings/page";
import { api } from "@/lib/api/client";

vi.mock("@/lib/api/client", () => ({
  api: { get: vi.fn(), patch: vi.fn() },
  ApiError: class ApiError extends Error {},
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
