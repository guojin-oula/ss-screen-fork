import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 30000,
  workers: 1,
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:5173",
    trace: "retain-on-failure",
    launchOptions: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE
      ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE }
      : undefined
  },
  projects: [
    { name: "mobile-375", use: { viewport: { width: 375, height: 812 }, hasTouch: true } },
    { name: "tablet-768", use: { viewport: { width: 768, height: 1024 }, hasTouch: true } },
    { name: "desktop-1024", use: { viewport: { width: 1024, height: 768 } } },
    { name: "desktop-1440", use: { viewport: { width: 1440, height: 900 } } }
  ]
});
