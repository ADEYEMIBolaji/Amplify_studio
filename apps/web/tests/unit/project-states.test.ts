import { describe, expect, it } from "vitest";
import { PROJECT_STATES } from "@/lib/api/types";

describe("PROJECT_STATES", () => {
  it("matches the FRD section 1.1 state machine order", () => {
    expect(PROJECT_STATES).toEqual([
      "idea",
      "scripting",
      "script_approved",
      "recorded",
      "subtitled",
      "ready",
      "scheduled",
      "published",
      "measured",
    ]);
  });
});
