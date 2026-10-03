import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const ENV = process.env.TAFWID_E2E_ENV ?? "placeholder";

// Poll on a timer: under software rendering, animation-frame polling crawls.
const worldReady = (page: Page, timeout = 60_000) =>
  page.waitForFunction(() => window.__tafwidWorldReady === true, null, { timeout, polling: 250 });

async function open(page: Page, extra = "") {
  await page.goto(`/?env=${ENV}${extra}`);
  await worldReady(page);
}

const badge = (page: Page, id: string) => page.locator(`.badge[data-agent="${id}"]`);
const rosterRow = (page: Page, id: string) => page.locator(`.roster-panel .agent-row[data-agent="${id}"]`);

// Reads the rect directly: badges can be momentarily hidden under HUD panels.
async function centre(page: Page, id: string) {
  const box = await badge(page, id).evaluate((el) => el.getBoundingClientRect().toJSON());
  return { x: box.x + box.width / 2, y: box.y + box.height };
}

test("shows sample data and stats", async ({ page }) => {
  await open(page);
  await expect(page.getByText("Sample data")).toBeVisible();
  const stats = page.locator(".stats");
  await expect(stats.locator(".stat-working strong")).toHaveText("2");
  await expect(stats.locator(".stat-review strong")).toHaveText("1");
  await expect(stats.locator(".stat-issue strong")).toHaveText("1");
});

test("falls back to the sample day with the live-off notice and groups the roster by team", async ({ page }) => {
  await open(page);
  await expect(page.getByRole("button", { name: "Sample", exact: true })).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByRole("button", { name: "Live", exact: true })).toHaveAttribute("aria-pressed", "false");
  await expect(page.locator(".live-notice")).toContainText("Live activity is off. Run");
  await expect(page.locator(".live-notice code")).toHaveText("python3 plugins/tafwid/skills/delegate/scripts/world.py on");
  await expect(page.locator(".roster-panel .team-heading")).toHaveText(["harbour-app· Claude Code", "orchard-api· Codex"]);
  // A project chip filters the roster; pressing it again clears the filter.
  const chip = page.locator('.team-chips .chip[data-project="orchard-api"]');
  await chip.click();
  await expect(page.locator(".roster-panel .agent-row")).toHaveCount(2);
  await chip.click();
  await expect(page.locator(".roster-panel .agent-row")).toHaveCount(5);
});

test("roster selection follows the agent and shows the follow card", async ({ page }) => {
  await open(page);
  await rosterRow(page, "noor").click();
  await expect(rosterRow(page, "noor")).toHaveAttribute("aria-pressed", "true");
  await expect(badge(page, "noor")).toHaveAttribute("aria-pressed", "true");
  const details = page.locator(".details");
  await expect(details).toContainText("Following");
  await expect(details).toContainText("Noor");
  // The camera glides to Noor: their badge ends up near the viewport centre.
  await expect
    .poll(async () => {
      const c = await centre(page, "noor");
      return Math.hypot(c.x - 720, c.y - 450);
    }, { timeout: 10_000 })
    .toBeLessThan(160);
  await page.keyboard.press("Escape");
  await expect(details).toBeHidden();
});

test("badge and roster selection stay in sync across a mode switch", async ({ page }) => {
  await open(page);
  await badge(page, "cleo").click();
  await page.getByRole("button", { name: "Dashboard" }).click();
  await expect(page.locator(".app")).toHaveAttribute("data-mode", "dashboard");
  await expect(rosterRow(page, "cleo")).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator(".details")).toContainText("In focus");
  await page.getByRole("button", { name: "Explore" }).click();
  await expect(badge(page, "cleo")).toHaveAttribute("aria-pressed", "true");
});

test("camera buttons change the compass heading", async ({ page }) => {
  await open(page);
  const cluster = page.locator(".camera-controls");
  const before = Number(await cluster.getAttribute("data-heading"));
  await page.getByRole("button", { name: "Rotate left (Q)" }).click();
  await expect.poll(async () => Number(await cluster.getAttribute("data-heading")) - before).toBeGreaterThan(1.4);
  await page.getByRole("button", { name: "Reset view" }).click();
  await expect.poll(async () => Math.abs(Number(await cluster.getAttribute("data-heading")) - before)).toBeLessThan(0.05);
});

test("badges stay attached to their characters after a resize", async ({ page }) => {
  await open(page);
  const viewportBox = async () => (await page.locator(".viewport").boundingBox())!;
  await page.setViewportSize({ width: 1100, height: 760 });
  await expect
    .poll(async () => {
      const c = await centre(page, "milo");
      const v = await viewportBox();
      return c.x > v.x && c.x < v.x + v.width && c.y > v.y && c.y < v.y + v.height;
    })
    .toBe(true);
});

test("step the sample day walks Ada to the review spot", async ({ page }) => {
  test.setTimeout(90_000);
  await open(page);
  const step = page.getByRole("button", { name: "Step the sample day" });
  await step.click(); // Rex starts fixing tests
  await step.click(); // Ada's change is ready for review
  await expect(rosterRow(page, "ada")).toContainText("Awaiting review");
  await expect
    .poll(async () => {
      const a = await centre(page, "ada"), c = await centre(page, "cleo");
      return Math.hypot(a.x - c.x, a.y - c.y);
    }, { timeout: 45_000 })
    .toBeLessThan(90);
});

test("no-WebGL fallback disables explore", async ({ page }) => {
  await page.goto(`/?env=${ENV}&forceNoWebGL`);
  await expect(page.locator(".app")).toHaveAttribute("data-mode", "dashboard");
  await expect(page.getByRole("button", { name: "Explore" })).toBeDisabled();
  await expect(page.locator(".world-status")).toContainText("The 3D world is unavailable on this device");
  await rosterRow(page, "ada").click();
  await expect(page.locator(".details")).toContainText("Building the account settings flow");
});

test("reduced motion stops ambient extras", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await open(page);
  await expect.poll(() => page.evaluate(() => window.__tafwidAmbientEnabled)).toBe(false);
});

test("an invalid package shows a named error", async ({ page }) => {
  await page.route("**/environments/**/manifest.json", (route) =>
    route.fulfill({ contentType: "application/json", body: JSON.stringify({ schema: "nope" }) }),
  );
  await page.goto(`/?env=${ENV}`);
  await expect(page.locator(".world-status")).toContainText('Invalid environment package: schema: expected "tafwid.environment/2"');
  await expect(rosterRow(page, "milo")).toBeVisible();
});

for (const mode of ["explore", "dashboard"] as const) {
  test(`axe finds no serious violations in ${mode} mode`, async ({ page }) => {
    await open(page, `&mode=${mode}`);
    await page.screenshot({ path: `test-results/evidence/${ENV}-${mode}.png` });
    const results = await new AxeBuilder({ page }).exclude(".world-canvas").analyze();
    const serious = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
    expect(serious.map((v) => `${v.id}: ${v.nodes.length}`)).toEqual([]);
  });
}

test("switching lighting variant while following keeps the selection", async ({ page }) => {
  test.setTimeout(240_000);
  await page.goto("/?env=cafe&variant=kit");
  await worldReady(page, 120_000);
  await rosterRow(page, "ada").click();
  await page.evaluate(() => (window.__tafwidWorldReady = false));
  await page.getByRole("button", { name: "Scene · baked light" }).click();
  await worldReady(page, 120_000);
  await expect(rosterRow(page, "ada")).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator(".details")).toContainText("Following");
  await expect(page.locator(".world-status")).toHaveAttribute("data-state", "ready");
});

test("reduced motion also stills foliage sway", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await open(page);
  await expect.poll(() => page.evaluate(() => window.__tafwidMotionScale)).toBe(0);
});

test("losing the graphics context falls back to dashboard mode", async ({ page }) => {
  await open(page, "&forceWebGL");
  await page.evaluate(() => {
    const gl = (document.querySelector(".world-canvas") as HTMLCanvasElement).getContext("webgl2");
    gl?.getExtension("WEBGL_lose_context")?.loseContext();
  });
  await expect(page.locator(".app")).toHaveAttribute("data-mode", "dashboard");
  await expect(page.getByRole("button", { name: "Explore" })).toBeDisabled();
  await expect(page.locator(".world-status")).toContainText("The 3D world is unavailable on this device");
});

test("keyboard selection keeps focus on the chosen roster row", async ({ page }) => {
  await open(page);
  await rosterRow(page, "ada").focus();
  await page.keyboard.press("Enter");
  await expect(rosterRow(page, "ada")).toHaveAttribute("aria-pressed", "true");
  await expect.poll(() => page.evaluate(() => (document.activeElement as HTMLElement)?.dataset.agent)).toBe("ada");
  await page.getByRole("button", { name: "Dashboard" }).focus();
  await page.keyboard.press("Enter");
  await expect.poll(() => page.evaluate(() => document.activeElement?.textContent)).toBe("Dashboard");
});

test("a fast double switch ends on the last chosen variant", async ({ page }) => {
  // Software rendering keeps the main thread busy compiling shaders for minutes.
  test.setTimeout(420_000);
  await page.goto("/?env=cafe&variant=kit");
  await worldReady(page, 120_000);
  await page.getByRole("button", { name: "Scene · baked light" }).click();
  await page.getByRole("button", { name: "Kit · real-time light" }).click();
  await expect(page.getByRole("button", { name: "Kit · real-time light" })).toHaveAttribute("aria-pressed", "true");
  await page.waitForTimeout(20_000);
  await expect.poll(() => page.evaluate(() => window.__tafwidLoadedVariant), { timeout: 240_000 }).toBe("kit");
});
