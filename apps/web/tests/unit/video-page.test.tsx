import { act, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import VideoStudioPage from "@/app/(dashboard)/projects/[id]/video/page";
import { api } from "@/lib/api/client";
import { isVertical916 } from "@/lib/media";
import type { MediaAsset, Transcript } from "@/lib/api/types";

vi.mock("@/lib/api/client", () => ({
  api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), putRaw: vi.fn() },
  ApiError: class ApiError extends Error {},
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "proj-1" }),
}));

function asset(overrides: Partial<MediaAsset>): MediaAsset {
  return {
    id: "src-1",
    project_id: "proj-1",
    kind: "source",
    status: "ready",
    duration_seconds: 42,
    width: 1080,
    height: 1920,
    metadata_json: {},
    download_url: "http://api/media/signed/src",
    created_at: "2026-10-15T09:00:00Z",
    ...overrides,
  };
}

const transcript = (reviewed: boolean): Transcript => ({
  id: "t-1",
  media_asset_id: "src-1",
  segments: [{ start: 0, end: 2, text: "Grace upon grace." }],
  reviewed_at: reviewed ? "2026-10-15T10:00:00Z" : null,
});

function mockApi(assets: MediaAsset[], t: Transcript) {
  vi.mocked(api.get).mockImplementation(async (path: string) => {
    if (path === "/api/projects/proj-1/media") return assets;
    if (path === "/api/media/src-1/transcript") return t;
    throw new Error(`unexpected GET ${path}`);
  });
}

describe("VideoStudioPage — FR-009 burn-in render (AT-03)", () => {
  beforeEach(() => vi.clearAllMocks());

  it("asks for reviewed subtitles before offering a render", async () => {
    mockApi([asset({})], transcript(false));
    render(<VideoStudioPage />);

    await waitFor(() => expect(screen.getByText(/Mark the subtitles reviewed first/)).toBeInTheDocument());
    expect(screen.queryByRole("button", { name: /render with captions/i })).not.toBeInTheDocument();
  });

  it("requires a crop/pad choice for a landscape source and sends it", async () => {
    mockApi([asset({ width: 1920, height: 1080 })], transcript(true));
    vi.mocked(api.post).mockResolvedValue({});
    render(<VideoStudioPage />);

    const button = await screen.findByRole("button", { name: /render with captions/i });
    expect(button).toBeDisabled();

    await act(async () => screen.getByLabelText("Blurred-background pad").click());
    expect(button).toBeEnabled();

    await act(async () => button.click());
    expect(api.post).toHaveBeenCalledWith("/api/media/src-1/render", { fit_mode: "pad" });
  });

  it("renders a 9:16 source without asking about fit", async () => {
    mockApi([asset({})], transcript(true));
    vi.mocked(api.post).mockResolvedValue({});
    render(<VideoStudioPage />);

    const button = await screen.findByRole("button", { name: /render with captions/i });
    expect(screen.queryByLabelText("Centre-crop")).not.toBeInTheDocument();
    await act(async () => button.click());
    expect(api.post).toHaveBeenCalledWith("/api/media/src-1/render", { fit_mode: null });
  });

  it("links the newest render and warns when captions weren't really burned in", async () => {
    mockApi(
      [
        asset({}),
        asset({
          id: "r-old",
          kind: "render",
          download_url: "http://api/media/signed/old",
          created_at: "2026-10-15T10:00:00Z",
        }),
        asset({
          id: "r-new",
          kind: "render",
          download_url: "http://api/media/signed/new",
          created_at: "2026-10-15T11:00:00Z",
          metadata_json: { degraded: true },
        }),
      ],
      transcript(true),
    );
    render(<VideoStudioPage />);

    const link = await screen.findByRole("link", { name: /download captioned mp4/i });
    expect(link).toHaveAttribute("href", "http://api/media/signed/new");
    expect(screen.getByText(/Captions were not burned in/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /render again/i })).toBeInTheDocument();
  });
});

describe("isVertical916", () => {
  it("matches the API's tolerance", () => {
    expect(isVertical916(1080, 1920)).toBe(true);
    expect(isVertical916(720, 1280)).toBe(true);
    expect(isVertical916(1920, 1080)).toBe(false);
    expect(isVertical916(1080, 1350)).toBe(false);
    expect(isVertical916(null, null)).toBe(false);
  });
});
