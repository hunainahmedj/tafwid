import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { expect, test, type Page } from "@playwright/test";
import { appendEvents, parseFixture, replay, setEnabled, type ReplayLine } from "../../scripts/replay-events";
import { badge, characters, ENV, open, resetWorld, rosterRow, worldReady } from "./helpers";
import { E2E_HOME } from "./home";

// Replays a fixture log through the real bridge (the web server's TAFWID_HOME
// is E2E_HOME) and checks what the dashboard shows. Fixture times are offsets
// from "now", so the replayed day is always recent.
const FIXTURE = parseFixture(readFileSync(fileURLToPath(new URL("./fixtures/events-sample.replay", import.meta.url)), "utf8"));

// The fixture's three teams: two on Claude Code, one on Codex.
const QUARRY = "a1b2c3d4e5f60718"; // quarry-sync: a builder and a reviewer under a coordinator
const MEADOW = "b2c3d4e5f6071829"; // meadow-cli: a tester
const LANTERN = "c3d4e5f607182930"; // lantern-docs (Codex): a documenter
const BUILDER = "1111aaaa2222bbbb";
const REVIEWER = "3333cccc4444dddd";
const TESTER = "5555eeee6666ffff";
const DOCUMENTER = "7777aaaa8888bbbb";
const FIXTURE_AGENTS = 7;
const SAMPLE_AGENT = "milo"; // a character of the sample day

const live = (page: Page) => page.getByRole("button", { name: "Live", exact: true });
const sample = (page: Page) => page.getByRole("button", { name: "Sample", exact: true });
const rosterRows = (page: Page) => page.locator(".roster-panel .agent-row");
const chip = (page: Page, project: string) => page.locator(`.team-chips .chip[data-project="${project}"]`);

/** Switch on, log replayed, page open on the live world. */
async function openLive(page: Page, extra = "") {
  setEnabled(E2E_HOME, true);
  replay(E2E_HOME, FIXTURE);
  await open(page, extra);
  await expect(live(page)).toHaveAttribute("aria-pressed", "true", { timeout: 15_000 });
  await expect(rosterRows(page)).toHaveCount(FIXTURE_AGENTS, { timeout: 15_000 });
}

test.describe("live activity", () => {
  // The bridge keeps its folded state, and the home is shared with the sample-day tests.
  test.beforeEach(({ request }) => resetWorld(request));
  test.afterEach(({ request }) => resetWorld(request));

  test("three replayed sessions become characters, rows and one team chip per project", async ({ page }) => {
    await openLive(page);
    await expect(page.locator(".live-notice")).toBeHidden();
    await expect(page.locator(".sample-pill")).toBeHidden();
    await expect.poll(() => characters(page), { timeout: 30_000 }).toBe(FIXTURE_AGENTS);

    await expect(page.locator(".roster-panel .team-heading")).toHaveText(["lantern-docs· Codex", "meadow-cli· Claude Code", "quarry-sync· Claude Code"]);
    await expect(page.locator(".team-chips .chip[data-project]")).toHaveCount(3);
    await expect(chip(page, "quarry-sync").locator(".chip-count")).toHaveText("3");
    await expect(chip(page, "meadow-cli").locator(".chip-count")).toHaveText("2");
    await expect(chip(page, "lantern-docs").locator(".chip-count")).toHaveText("2");

    // Roles and tasks come from the spawn events; every agent has just been active.
    await expect(rosterRow(page, BUILDER)).toContainText("Builder");
    await expect(rosterRow(page, BUILDER)).toContainText("Implement the cache layer");
    await expect(rosterRow(page, REVIEWER)).toContainText("Reviewer");
    await expect(rosterRow(page, TESTER)).toContainText("Tester");
    await expect(rosterRow(page, DOCUMENTER)).toContainText("Documenter");
    await expect(rosterRow(page, QUARRY)).toContainText("Coordinator");
    await expect(page.locator(".stats .stat-working strong")).toHaveText(String(FIXTURE_AGENTS));
  });

  test("a permission request raises an attention beacon, and the next prompt clears it", async ({ page }) => {
    await openLive(page);
    await expect(rosterRow(page, MEADOW)).toContainText("Working");
    await expect(page.locator(".stats .stat-issue strong")).toHaveText("0");

    appendEvents(E2E_HOME, [{ session: MEADOW, project: "meadow-cli", event: "permission", dt: 0 }]);
    // The world raises its "!" beacon for agents whose status is "issue".
    await expect(rosterRow(page, MEADOW)).toContainText("Needs attention", { timeout: 10_000 });
    await expect(badge(page, MEADOW)).toHaveAttribute("data-status", "issue");
    await expect(page.locator(".stats .stat-issue strong")).toHaveText("1");
    await expect(badge(page, QUARRY)).toHaveAttribute("data-status", "working");

    appendEvents(E2E_HOME, [{ session: MEADOW, project: "meadow-cli", event: "prompt", dt: 0 }]);
    await expect(rosterRow(page, MEADOW)).toContainText("Working", { timeout: 10_000 });
    await expect(badge(page, MEADOW)).toHaveAttribute("data-status", "working");
    await expect(page.locator(".stats .stat-issue strong")).toHaveText("0");
  });

  test("a completed sub-agent is shown done, then leaves the roster within 30 s and the world after its walk out", async ({ page }) => {
    // The walk out advances by at most 0.25 s of world time per frame, so under software rendering it needs real time to spare.
    test.setTimeout(120_000);
    await openLive(page);
    await expect.poll(() => characters(page), { timeout: 30_000 }).toBe(FIXTURE_AGENTS);

    const stopped = Date.now();
    appendEvents(E2E_HOME, [{ session: QUARRY, project: "quarry-sync", event: "subagent-stop", agent: REVIEWER, agentType: "reviewer", status: "done", dt: 0 }]);
    await expect(rosterRow(page, REVIEWER)).toContainText("Done", { timeout: 10_000 });
    await expect(page.locator(".stats .stat-done strong")).toHaveText("1");

    // The bridge drops it 20 s after it finished. That bound is on the data, so it is held to 30 s.
    await expect(rosterRow(page, REVIEWER)).toHaveCount(0, { timeout: 30_000 });
    expect((Date.now() - stopped) / 1000).toBeLessThan(30);
    // The character walks to its coordinator, then out; how long that takes depends on the frame rate.
    await expect.poll(() => characters(page), { timeout: 60_000 }).toBe(FIXTURE_AGENTS - 1);

    // Only that sub-agent went: its coordinator and the other teams stay.
    await expect(rosterRows(page)).toHaveCount(FIXTURE_AGENTS - 1);
    await expect(rosterRow(page, QUARRY)).toBeVisible();
    await expect(rosterRow(page, BUILDER)).toBeVisible();
  });

  test("the project filter hides the other teams in the roster but not in the world", async ({ page }) => {
    await openLive(page);
    await expect.poll(() => characters(page), { timeout: 30_000 }).toBe(FIXTURE_AGENTS);

    await chip(page, "meadow-cli").click();
    await expect(chip(page, "meadow-cli")).toHaveAttribute("aria-pressed", "true");
    await expect(rosterRows(page)).toHaveCount(2);
    await expect(page.locator(".roster-panel .team-heading")).toHaveText(["meadow-cli· Claude Code"]);
    await expect(page.locator(".roster-panel .count")).toHaveText("2");
    await expect(rosterRow(page, QUARRY)).toHaveCount(0);
    await expect(rosterRow(page, LANTERN)).toHaveCount(0);
    expect(await characters(page)).toBe(FIXTURE_AGENTS);

    await chip(page, "meadow-cli").click();
    await expect(rosterRows(page)).toHaveCount(FIXTURE_AGENTS);
    await expect(page.locator(".roster-panel .team-heading")).toHaveCount(3);
  });

  test("40 agents in one project show +8 more under the cap of 32", async ({ page }) => {
    const GRANITE = "d4e5f60718293a4b";
    const subAgent = (i: number) => `${i.toString(16).padStart(4, "0")}00000000beef`;
    // One coordinator and 39 sub-agents, started a second apart. The 32 newest are kept; the coordinator and the 7 oldest are not.
    const crowd: ReplayLine[] = [
      { session: GRANITE, project: "granite-batch", event: "session", dt: -100 },
      { session: GRANITE, project: "granite-batch", event: "prompt", dt: -95 },
      ...Array.from({ length: 39 }, (_, i): ReplayLine => ({ session: GRANITE, project: "granite-batch", event: "subagent-start", agent: subAgent(i), agentType: "general-purpose", dt: -90 + i })),
    ];
    setEnabled(E2E_HOME, true);
    replay(E2E_HOME, crowd);
    await open(page);

    await expect(rosterRows(page)).toHaveCount(32, { timeout: 15_000 });
    await expect(page.locator(".roster-panel .more")).toHaveText("+8 more in granite-batch");
    await expect(page.locator(".roster-panel .team-group")).toHaveCount(1);
    await expect(chip(page, "granite-batch").locator(".chip-count")).toHaveText("40");
    await expect.poll(() => characters(page), { timeout: 45_000 }).toBe(32);
    await expect(rosterRow(page, subAgent(38))).toBeVisible();
    await expect(rosterRow(page, subAgent(6))).toHaveCount(0);
    await expect(rosterRow(page, GRANITE)).toHaveCount(0);
  });

  test("with the switch off, the notice appears and the sample day is shown", async ({ page }) => {
    replay(E2E_HOME, FIXTURE); // a log exists, but the switch was never turned on
    await open(page);

    await expect(page.locator(".live-notice")).toContainText("Live activity is off. Run");
    await expect(page.locator(".live-notice code")).toHaveText("python3 plugins/tafwid/skills/delegate/scripts/world.py on");
    await expect(sample(page)).toHaveAttribute("aria-pressed", "true");
    await expect(live(page)).toHaveAttribute("aria-pressed", "false");
    await expect(live(page)).toHaveAttribute("title", "Live activity is off. Choosing Live checks again.");
    await expect(page.locator(".sample-pill")).toBeVisible();
    await expect(page.getByRole("button", { name: "Step the sample day" })).toBeVisible();
    await expect(rosterRow(page, SAMPLE_AGENT)).toBeVisible();
    await expect(rosterRow(page, QUARRY)).toHaveCount(0);
    await expect(chip(page, "quarry-sync")).toHaveCount(0);
  });

  test("the Live and Sample buttons switch the data source", async ({ page }) => {
    await openLive(page);

    await sample(page).click();
    await expect(sample(page)).toHaveAttribute("aria-pressed", "true");
    await expect(page.locator(".sample-pill")).toBeVisible();
    await expect(rosterRow(page, SAMPLE_AGENT)).toBeVisible();
    await expect(rosterRow(page, QUARRY)).toHaveCount(0);
    await expect(page.locator(".live-notice")).toBeHidden();

    await live(page).click();
    await expect(live(page)).toHaveAttribute("aria-pressed", "true");
    await expect(page.locator(".sample-pill")).toBeHidden();
    await expect(rosterRows(page)).toHaveCount(FIXTURE_AGENTS);
    await expect(rosterRow(page, SAMPLE_AGENT)).toHaveCount(0);
    await expect(chip(page, "quarry-sync")).toBeVisible();
  });

  test("turning the switch off while watching returns to the sample day, and on again lets Live back in", async ({ page }) => {
    await openLive(page);

    setEnabled(E2E_HOME, false);
    await expect(sample(page)).toHaveAttribute("aria-pressed", "true", { timeout: 10_000 });
    await expect(page.locator(".live-notice")).toContainText("Live activity is off. Run");

    setEnabled(E2E_HOME, true);
    await live(page).click(); // Live stays pressable while off: it asks the bridge again
    await expect(live(page)).toHaveAttribute("aria-pressed", "true", { timeout: 10_000 });
    await expect(page.locator(".live-notice")).toBeHidden();
    await expect(rosterRows(page)).toHaveCount(FIXTURE_AGENTS);
  });

  test("a page that opens straight into live activity draws the world while the host reports it hidden", async ({ page }) => {
    // Some hosts (the Claude desktop browser pane) report document.hidden while
    // they keep painting the page and running animation frames. The world must
    // still render there: the browser pauses animation frames for a truly hidden tab.
    await page.addInitScript(() => {
      Object.defineProperty(Document.prototype, "hidden", { configurable: true, get: () => true });
      Object.defineProperty(Document.prototype, "visibilityState", { configurable: true, get: () => "hidden" });
    });
    const CODEX = "c0de0000c0de0000";
    setEnabled(E2E_HOME, true);
    replay(E2E_HOME, [
      { session: CODEX, host: "codex", project: "lantern", event: "session", dt: -30 },
      { session: CODEX, host: "codex", project: "lantern", event: "prompt", dt: -20 },
    ]);
    await page.goto(`/?env=${ENV}`);
    await worldReady(page);
    await expect(live(page)).toHaveAttribute("aria-pressed", "true", { timeout: 15_000 });
    await expect(rosterRow(page, CODEX)).toContainText("Coordinator");

    await expect.poll(() => page.evaluate(() => window.__tafwidStats?.().calls ?? 0), { timeout: 15_000 }).toBeGreaterThan(0);
    // The badge is projected above the character: a finite position, off the top-left corner.
    const badgeAt = () =>
      badge(page, CODEX).evaluate((el) => {
        const m = /translate\(([^,]+)px, ([^)]+)px\)/.exec(el.style.transform);
        return m ? [Number(m[1]), Number(m[2])] : null;
      });
    await expect.poll(badgeAt, { timeout: 15_000 }).not.toBeNull();
    const [x, y] = (await badgeAt())!;
    expect(Number.isFinite(x) && Number.isFinite(y)).toBe(true);
    expect(x > 1 || y > 1).toBe(true);
    const box = (await badge(page, CODEX).boundingBox())!;
    expect(box.x > 1 || box.y > 1).toBe(true);
  });
});
