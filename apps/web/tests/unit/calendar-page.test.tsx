import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import CalendarPage from "@/app/(dashboard)/calendar/page";
import { api } from "@/lib/api/client";

vi.mock("@/lib/api/client", () => ({
  api: { get: vi.fn(), patch: vi.fn(), post: vi.fn() },
  ApiError: class ApiError extends Error {},
}));

describe("CalendarPage", () => {
  it("shows an empty state when there are no planned posts", async () => {
    vi.mocked(api.get).mockResolvedValue([]);

    render(<CalendarPage />);

    await waitFor(() => expect(screen.getByText(/no planned posts yet/i)).toBeInTheDocument());
  });

  it("lists a scheduled post with its platform and status", async () => {
    vi.mocked(api.get).mockResolvedValue([
      {
        id: "post1",
        project_id: "proj1",
        workspace_id: "w1",
        platform: "instagram",
        caption: "Hello world",
        hashtags: ["#faith"],
        cta: "Follow",
        media_asset_id: null,
        status: "draft",
        scheduled_at: "2026-06-15T08:00:00Z",
        timezone: "Europe/London",
        posting_slot: "morning",
        published_at: null,
        external_post_id: null,
        external_url: null,
        is_historical: false,
        created_at: "2026-06-01T00:00:00Z",
        updated_at: "2026-06-01T00:00:00Z",
      },
    ]);

    render(<CalendarPage />);

    await waitFor(() => expect(screen.getByText("instagram")).toBeInTheDocument());
    expect(screen.getByText("Hello world")).toBeInTheDocument();
    expect(screen.getByText("draft")).toBeInTheDocument();
  });
});
