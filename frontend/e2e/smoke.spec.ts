import { expect, test } from "@playwright/test";

test("atlas renders offline, map has every state, region opens a record", async ({ page, context }) => {
  // Block everything except our own origin so an accidental network dependency fails loudly.
  await context.route("**/*", (route) => {
    const u = new URL(route.request().url());
    if (u.hostname === "localhost" || u.hostname === "127.0.0.1") return route.continue();
    return route.abort();
  });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Bust Atlas/ })).toBeVisible();
  const states = page.locator("svg.map path.state");
  await expect(states).toHaveCount(35);
  await page.locator("svg.map path.state[data-region='central']").first().dispatchEvent("click");
  await expect(page.getByRole("heading", { name: "Central India" })).toBeVisible();
  await expect(page.getByText(/bust rate/)).toBeVisible();
});

test("today mode shows a forecaster's note and evidence has a reliability diagram", async ({ page }) => {
  await page.goto("/?mode=today&lead=6");
  await expect(page.locator("svg.map path.state")).toHaveCount(35);
  await page.locator("svg.map path.state[data-region='north_west']").first().dispatchEvent("click");
  await expect(page.getByRole("heading", { name: "Forecaster's note" })).toBeVisible();
  await expect(page.locator(".note p")).toHaveCount(3);
  await page.goto("/?mode=evidence");
  await expect(page.getByRole("img", { name: "Reliability diagram" })).toBeVisible();
});
