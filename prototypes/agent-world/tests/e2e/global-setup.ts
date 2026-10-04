import { mkdirSync, rmSync } from "node:fs";
import { E2E_HOME } from "./home";

// Start every run from an empty home, before the web server first reads it.
export default function globalSetup() {
  rmSync(E2E_HOME, { recursive: true, force: true });
  mkdirSync(E2E_HOME, { recursive: true });
}
