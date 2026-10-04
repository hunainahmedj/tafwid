import { rmSync } from "node:fs";
import type { APIRequestContext, Page } from "@playwright/test";
import { appendEvents, setEnabled, worldDir } from "../../scripts/replay-events";
import { E2E_HOME } from "./home";

export const ENV = process.env.TAFWID_E2E_ENV ?? "placeholder";

// Poll on a timer: under software rendering, animation-frame polling crawls.
export const worldReady = (page: Page, timeout = 60_000) =>
  page.waitForFunction(() => window.__tafwidWorldReady === true, null, { timeout, polling: 250 });

export async function open(page: Page, extra = "") {
  await page.goto(`/?env=${ENV}${extra}`);
  await worldReady(page);
}

export const badge = (page: Page, id: string) => page.locator(`.badge[data-agent="${id}"]`);
export const rosterRow = (page: Page, id: string) => page.locator(`.roster-panel .agent-row[data-agent="${id}"]`);

/** Characters the 3D world is keeping, including any still walking out. */
export const characters = (page: Page) => page.evaluate(() => window.__tafwidStats?.().characters ?? -1);

interface BridgeSnapshot {
  enabled: boolean;
  state: { teams: Record<string, unknown> };
}

/**
 * Puts the e2e home and the running bridge back to nothing: the switch off, no
 * log, no teams. The bridge keeps its folded state between tests, so each
 * team's session is ended first; asking for the snapshot makes it poll.
 */
export async function resetWorld(request: APIRequestContext) {
  const read = async () => (await (await request.get("/api/world/snapshot")).json()) as BridgeSnapshot;
  setEnabled(E2E_HOME, false);
  const sessions = Object.keys((await read()).state.teams);
  if (sessions.length) {
    appendEvents(E2E_HOME, sessions.map((session) => ({ session, event: "session-end", dt: 0 })));
    await read();
  }
  rmSync(worldDir(E2E_HOME), { recursive: true, force: true });
  const { state } = await read(); // a poll with no log folder lets the tailer forget its offsets
  if (Object.keys(state.teams).length) throw new Error("the bridge still holds teams after a reset");
}
