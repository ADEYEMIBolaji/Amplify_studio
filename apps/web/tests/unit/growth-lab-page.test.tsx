import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import GrowthLabPage from "@/app/(dashboard)/growth-lab/page";
import { api } from "@/lib/api/client";

vi.mock("@/lib/api/client", () => ({
  api: { get: vi.fn(), post: vi.fn() },
  ApiError: class ApiError extends Error {
    code?: string;
    constructor(message: string, code?: string) {
      super(message);
      this.code = code;
    }
  },
}));

const baseMetrics = {
  platform: "instagram",
  start: "2026-06-01T00:00:00Z",
  end: "2026-06-29T00:00:00Z",
  target_day: 7,
  window_days: 1,
  reach_median: null,
  reach_mean: null,
  engagement_per_reach: null,
  share_rate: null,
  save_rate: null,
  watch_seconds_avg: null,
  completion_rate: null,
  net_follower_change: null,
  net_follower_change_low_confidence: false,
  followers_per_1000_reached: null,
  posting_adherence: null,
  data_coverage: { eligible: 0, total: 0 },
  low_sample: false,
};

describe("GrowthLabPage", () => {
  it("shows Unavailable for missing metrics rather than zero", async () => {
    vi.mocked(api.get).mockImplementation((path: string) => {
      if (path.startsWith("/api/analytics/overview")) {
        return Promise.resolve({ current: baseMetrics, previous: baseMetrics });
      }
      return Promise.resolve([]);
    });

    render(<GrowthLabPage />);

    await waitFor(() => expect(screen.getAllByText("Unavailable").length).toBeGreaterThan(0));
    expect(screen.queryByText("0.0")).not.toBeInTheDocument();
  });

  it("shows the low-sample warning on the 7-day range", async () => {
    vi.mocked(api.get).mockImplementation((path: string) => {
      if (path.startsWith("/api/analytics/overview")) {
        return Promise.resolve({
          current: { ...baseMetrics, low_sample: true },
          previous: baseMetrics,
        });
      }
      return Promise.resolve([]);
    });

    render(<GrowthLabPage />);

    await waitFor(() => expect(screen.getByText(/low sample size/i)).toBeInTheDocument());
  });
});
