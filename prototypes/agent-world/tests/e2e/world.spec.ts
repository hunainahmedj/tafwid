import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const ENV = process.env.TAFWID_E2E_ENV ?? "placeholder";

async function open(page: Page, extra = "") {
  await page.goto(`/?env=${ENV}${extra}`);
  await page.waitForFunction(() => window.__tafwidWorldReady === true, null, { timeout: 30_000 });
}

const badge = (page: Page, id: string) => page.locator(`.badge[data-agent="${id}"]`);
const rosterRow = (page: Page, id: string) => page.locator(`.roster-panel .agent-row[data-agent="${id}"]`);

async function centre(page: Page, id: string) {
  const box = await badge(page, id).boundingBox();
  if (!box) throw new Error(`badge ${id} not visible`);
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
  await expect(page.locator(".world-status")).toContainText('Invalid environment package: schema: expected "tafwid.environment/1"');
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
  test.setTimeout(120_000);
  await page.goto("/?env=cafe&variant=kit");
  await page.waitForFunction(() => window.__tafwidWorldReady === true, null, { timeout: 60_000 });
  await rosterRow(page, "ada").click();
  await page.evaluate(() => (window.__tafwidWorldReady = false));
  await page.getByRole("button", { name: "Scene · baked light" }).click();
  await page.waitForFunction(() => window.__tafwidWorldReady === true, null, { timeout: 60_000 });
  await expect(rosterRow(page, "ada")).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator(".details")).toContainText("Following");
  await expect(page.locator(".world-status")).toHaveAttribute("data-state", "ready");
});
