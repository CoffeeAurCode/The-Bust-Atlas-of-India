import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  use: { baseURL: process.env.BASE_URL ?? "http://localhost:4173", viewport: { width: 1366, height: 768 } },
  webServer: process.env.BASE_URL ? undefined : { command: "npm run preview -- --port 4173 --strictPort", url: "http://localhost:4173", reuseExistingServer: true, timeout: 60_000 },
});
