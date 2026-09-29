import AxeBuilder from "@axe-core/playwright";
import { test, expect } from "@playwright/test";
test("room and roster selection stay in sync", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /Ada Builder/ }).click();
  await expect(page.locator(".details h2")).toHaveText("Ada Builder");
  await expect(
    page.getByRole("button", { name: "Select Ada in office" }),
  ).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("button", { name: "Attention", exact: true }).click();
  await expect(page.locator(".details h2")).toHaveText("Cleo Reviewer");
  await page.getByRole("button", { name: "Select Milo in office" }).click();
  await expect(
    page.getByRole("button", { name: "All agents", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator(".details h2")).toHaveText("Milo Coordinator");
});
test("room updates with empty scenario", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Demo scenario").selectOption("empty");
  await expect(page.locator(".scene-host")).toHaveAttribute(
    "aria-label",
    "Agent office: no agents",
  );
  await expect(page.locator(".scene-label")).toHaveCount(0);
  await expect(
    page.getByRole("heading", { name: "A fresh start" }),
  ).toBeVisible();
});
test("WebGL unavailable preserves useful controls", async ({ page }) => {
  await page.addInitScript(() => {
    const original = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function (
      type: string,
      ...args: unknown[]
    ) {
      if (type.includes("webgl")) return null;
      return original.apply(this, [type, ...args] as never);
    } as typeof original;
  });
  await page.goto("/");
  await expect(page.getByText("The 3D view is unavailable")).toBeVisible();
  await page.getByRole("button", { name: /Noor Researcher/ }).click();
  await expect(page.locator(".details h2")).toHaveText("Noor Researcher");
});
test("a character remains pickable after resizing", async ({ page }) => {
  await page.goto("/");
  for (const width of [1440, 1000]) {
    await page.setViewportSize({ width, height: 1000 });
    await page.getByRole("button", { name: /Milo Coordinator/ }).click();
    const label = page.getByRole("button", { name: "Select Ada in office" });
    await expect(label).toBeVisible();
    // The character is just above and right of its projected nameplate.
    const box = await label.boundingBox();
    const canvas = await page.locator("canvas").boundingBox();
    const scale = canvas!.width / 829;
    await page.mouse.click(
      box!.x + box!.width / 2 + 12 * scale,
      box!.y - 25 * scale,
    );
    await expect(page.locator(".details h2")).toHaveText("Ada Builder");
  }
});
test("initial desktop view includes selected details and fits horizontally", async ({
  page,
}, info) => {
  await page.goto("/");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  if (info.project.name === "desktop") {
    const details = await page.locator(".details").boundingBox();
    expect(details!.y + details!.height).toBeLessThanOrEqual(1000);
  }
});
test("scenarios keep numbers honest and keyboard selection keeps focus", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.getByText("Sample data", { exact: true })).toBeVisible();
  await expect(page.locator("[data-metric=working]")).toHaveText("02");
  await expect(page.locator("[data-metric=review]")).toHaveText("01");
  await expect(page.locator("[data-metric=completed]")).toHaveText("07");
  const ada = page.getByRole("button", { name: /Ada Builder/ });
  await ada.focus();
  await page.keyboard.press("Enter");
  await expect(ada).toBeFocused();
  await expect(page.locator(".details h2")).toHaveText("Ada Builder");
  await page.getByLabel("Demo scenario").selectOption("unavailable");
  await expect(page.locator(".notice")).toBeVisible();
  await expect(page.locator("[data-metric=working]")).toHaveText("—");
  await expect(page.locator("[data-metric=review]")).toHaveText("—");
  await expect(page.locator("[data-metric=completed]")).toHaveText("04");
  await page.getByRole("button", { name: /Ada Builder/ }).click();
  await expect(page.locator(".details")).toContainText(
    "Waiting for access to the project dependencies",
  );
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.getByLabel("Demo scenario").selectOption("empty");
  await expect(page.locator("[data-metric=completed]")).toHaveText("00");
});
test("context loss keeps the roster usable", async ({ page }) => {
  await page.goto("/");
  await page.locator("canvas").waitFor();
  await page.locator("canvas").evaluate((canvas: HTMLCanvasElement) => {
    canvas
      .getContext("webgl2")!
      .getExtension("WEBGL_lose_context")!
      .loseContext();
  });
  await expect(page.getByText("The 3D view is unavailable")).toBeVisible();
  await page.getByRole("button", { name: /Cleo Reviewer/ }).click();
  await expect(page.locator(".details")).toContainText(
    "does not mean the result has been accepted",
  );
});
test("reduced motion and filtered emptiness remain usable", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await page.getByRole("button", { name: "Working", exact: true }).click();
  await expect(page.locator(".agent-card")).toHaveCount(2);
  await page.getByLabel("Demo scenario").selectOption("empty");
  await page.getByRole("button", { name: "Working", exact: true }).click();
  await expect(page.locator(".agent-card")).toHaveCount(0);
  await expect(page.locator(".detail-empty")).toBeVisible();
});
test("dashboard survives a failed scene download", async ({ page }) => {
  await page.route("**/src/office.ts*", (route) => route.abort());
  await page.goto("/");
  await expect(page.getByText("The 3D view is unavailable")).toBeVisible();
  await page.getByRole("button", { name: /Ada Builder/ }).click();
  await expect(page.locator(".details h2")).toHaveText("Ada Builder");
});
test("visible dashboard states pass automated accessibility checks", async ({
  page,
}) => {
  await page.goto("/");
  for (const scenario of ["active", "unavailable", "empty"]) {
    await page.getByLabel("Demo scenario").selectOption(scenario);
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
      .analyze();
    expect(
      results.violations.map((v) => ({
        id: v.id,
        nodes: v.nodes.map((n) => ({
          target: n.target,
          summary: n.failureSummary,
        })),
      })),
    ).toEqual([]);
  }
});

test("long status and elapsed time remain inside narrow mobile cards", async ({
  page,
}) => {
  await page.setViewportSize({ width: 320, height: 844 });
  await page.goto("/");
  await page.getByLabel("Demo scenario").selectOption("unavailable");
  for (const card of await page.locator(".agent-card").all()) {
    const bounds = await card.boundingBox();
    for (const text of await card.locator(".status, .elapsed").all()) {
      const textBounds = await text.boundingBox();
      expect(textBounds!.x + textBounds!.width).toBeLessThanOrEqual(
        bounds!.x + bounds!.width,
      );
    }
  }
});
