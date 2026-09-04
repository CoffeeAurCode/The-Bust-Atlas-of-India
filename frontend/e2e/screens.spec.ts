import { test } from "@playwright/test";

const OUT = process.env.SHOT_DIR ?? "test-results/shots";
const views = [
  ["atlas", "/?mode=atlas&season=JJAS&lead=5"],
  ["atlas-region", "/?mode=atlas&season=JJAS&lead=5&region=central"],
  ["today", "/?mode=today&lead=6"],
  ["today-region", "/?mode=today&lead=6&region=north_west"],
  ["evidence", "/?mode=evidence"],
  ["cases", "/?mode=cases"],
] as const;

for (const theme of ["light", "dark"] as const) {
  for (const [name, url] of views) {
    test(`${name} ${theme}`, async ({ page }) => {
      await page.emulateMedia({ colorScheme: theme });
      await page.goto(url);
      await page.waitForSelector("svg.map path.state, .page", { timeout: 15000 });
      await page.waitForTimeout(900);
      await page.screenshot({ path: `${OUT}/${name}-${theme}.png`, fullPage: false });
    });
  }
}
