import { defineConfig } from "@playwright/test";
import { E2E_HOME } from "./tests/e2e/home";

// The e2e server has its own port and its own TAFWID_HOME, and is never reused:
// a dev server on :4174 reads the real ~/.tafwid and would break the live tests.
const PORT = 4175;
const ORIGIN = `http://127.0.0.1:${PORT}`;

export default defineConfig({
  testDir: "./tests/e2e",
  globalSetup: "./tests/e2e/global-setup.ts",
  fullyParallel: false,
  workers: 1,
  timeout: 60_000,
  webServer: {
    command: `npx vite --host 127.0.0.1 --port ${PORT} --strictPort`,
    url: ORIGIN,
    reuseExistingServer: false,
    env: { TAFWID_HOME: E2E_HOME },
  },
  reporter: "list",
  use: {
    baseURL: ORIGIN,
    viewport: { width: 1440, height: 900 },
    launchOptions: { args: ["--enable-unsafe-swiftshader", "--use-angle=swiftshader"] },
  },
});
