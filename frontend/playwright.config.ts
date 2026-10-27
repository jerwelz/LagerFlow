import { defineConfig, devices } from "@playwright/test";

// Local run: builds nothing itself; run `npm run build` first so FastAPI can serve the dashboard.
// Against the deployed demo: BASE_URL=https://... npm run e2e
const port = process.env.E2E_PORT ?? "8765";
const baseURL = process.env.BASE_URL ?? `http://127.0.0.1:${port}`;

export default defineConfig({
  testDir: "e2e",
  timeout: 90_000,
  expect: { timeout: 15_000 },
  retries: 0,
  reporter: "list",
  use: { baseURL, trace: "retain-on-failure", locale: "de-DE" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: process.env.BASE_URL
    ? undefined
    : {
        command: "node e2e/start-server.mjs",
        url: `${baseURL}/health`,
        reuseExistingServer: false,
        timeout: 60_000,
      },
});
