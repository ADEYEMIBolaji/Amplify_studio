import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import DashboardPage from "@/app/(dashboard)/dashboard/page";
import { api } from "@/lib/api/client";
import { HomeDashboard } from "@/lib/api/types";

vi.mock("@/lib/api/client", () => ({
  api: { get: vi.fn() },
  ApiError: class ApiError extends Error {},
}));

const emptyDashboard: HomeDashboard = {
  next_actions: [],
  pipeline_counts: {},
  posting_adherence_this_week: null,
  posting_adherence_last_week: null,
  last_follower_snapshot_at: { instagram: null, tiktok: null, facebook: null, x: null },
  reach_trend: { instagram: [], tiktok: [], facebook: [], x: [] },
  follower_trend: { instagram: [], tiktok: [], facebook: [], x: [] },
  active_experiments: [],
};

describe("DashboardPage", () => {
  it("shows an empty state with a create-project link when there are no active projects", async () => {
    vi.mocked(api.get).mockResolvedValue(emptyDashboard);

    render(<DashboardPage />);

    expect(screen.getByText(/loading/i)).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText(/no active projects yet/i)).toBeInTheDocument());
    expect(screen.getByRole("link", { name: /create your first project/i })).toBeInTheDocument();
  });

  it("lists next actions and pipeline counts once loaded", async () => {
    vi.mocked(api.get).mockResolvedValue({
      ...emptyDashboard,
      next_actions: [
        { project_id: "1", title: "Faith talk", status: "idea", next_action: "Generate a script" },
      ],
      pipeline_counts: { idea: 2, scripting: 1 },
    });

    render(<DashboardPage />);

    await waitFor(() => expect(screen.getByText("Faith talk")).toBeInTheDocument());
    expect(screen.getByText("Generate a script")).toBeInTheDocument();
    expect(screen.getByText("Idea")).toBeInTheDocument();
  });

  it("shows unavailable (not 0%) posting adherence when there's nothing scheduled", async () => {
    vi.mocked(api.get).mockResolvedValue(emptyDashboard);

    render(<DashboardPage />);

    await waitFor(() => expect(screen.getByText("This week")).toBeInTheDocument());
    expect(screen.getAllByText("—")).toHaveLength(2);
  });
});
