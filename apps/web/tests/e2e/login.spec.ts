import { expect, test } from "@playwright/test";

/**
 * Smoke test for the one screen that works without a live Supabase project.
 * The full idea -> script -> teleprompter flow (FR-002 through FR-006) needs
 * real Supabase auth to run end to end — see docs/plan.md Week 2 notes for
 * why that spec isn't here yet, and add it once a project is linked.
 */
test("unauthenticated visitors are redirected to login and see the sign-in form", async ({ page }) => {
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole("heading", { name: /sign in to amplify studio/i })).toBeVisible();
  await expect(page.getByLabel(/email/i)).toBeVisible();
  await expect(page.getByLabel(/password/i)).toBeVisible();
});
