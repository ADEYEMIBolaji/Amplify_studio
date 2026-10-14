import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import DashboardPage from "@/app/(dashboard)/dashboard/page";
import { api } from "@/lib/api/client";

vi.mock("@/lib/api/client", () => ({
  api: { get: vi.fn() },
  ApiError: class ApiError extends Error {},
}));

describe("DashboardPage", () => {
  it("shows an empty state with a create-project link when there are no projects", async () => {
    vi.mocked(api.get).mockResolvedValue([]);

    render(<DashboardPage />);

    expect(screen.getByText(/loading/i)).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText(/no projects yet/i)).toBeInTheDocument());
    expect(screen.getByRole("link", { name: /create your first project/i })).toBeInTheDocument();
  });

  it("groups projects by state once loaded", async () => {
    vi.mocked(api.get).mockResolvedValue([
      { id: "1", status: "idea" },
      { id: "2", status: "idea" },
      { id: "3", status: "scripting" },
    ]);

    render(<DashboardPage />);

    await waitFor(() => expect(screen.getByText("Idea")).toBeInTheDocument());
    const ideaCount = screen.getByText("Idea").previousElementSibling;
    expect(ideaCount).toHaveTextContent("2");
  });
});
