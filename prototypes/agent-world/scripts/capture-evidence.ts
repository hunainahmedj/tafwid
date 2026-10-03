// Captures critique evidence for one variant: screenshots and per-tier frame times.
// Usage: tsx scripts/capture-evidence.ts <kit|baked> <out-dir>   (dev server on :4174)
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { chromium, type Page } from "@playwright/test";

const [variant = "kit", outDir = ".critique/latest"] = process.argv.slice(2);
const dir = join(outDir, variant);
mkdirSync(dir, { recursive: true });

const browser = await chromium.launch({
  headless: true,
  args: ["--enable-gpu", "--ignore-gpu-blocklist", "--use-angle=metal"],
});
const page = await browser.newPage({ viewport: { width: 1600, height: 1000 }, deviceScaleFactor: 2 });
const notes: Record<string, unknown> = { variant };

async function settle(p: Page, ms = 2500) {
  await p.waitForTimeout(ms);
}

async function shot(name: string) {
  await page.screenshot({ path: join(dir, `${name}.png`) });
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

await page.goto(`http://127.0.0.1:4174/?env=cafe&variant=${variant}`);
await page.waitForFunction(() => window.__tafwidWorldReady === true, null, { timeout: 120_000 });
notes.renderer = await page.evaluate(() => {
  const c = document.createElement("canvas").getContext("webgl2");
  const d = c?.getExtension("WEBGL_debug_renderer_info");
  return d ? c!.getParameter(d.UNMASKED_RENDERER_WEBGL) : "unknown";
});
await page.selectOption(".quality", "high");
await settle(page, 4000);
await shot("01-explore-home");

// Frame times per tier (rolling window of 120 frames after a short warm-up).
const perf: Record<string, unknown> = {};
for (const tier of ["high", "medium", "low"]) {
  await page.selectOption(".quality", tier);
  await sleep(4500);
  perf[tier] = await page.evaluate(() => window.__tafwidPerf?.());
}
notes.frameTimes = perf;
await page.selectOption(".quality", "high");
await settle(page);

const zoom = async (times: number, button: "Zoom in" | "Zoom out") => {
  for (let i = 0; i < times; i++) await page.getByRole("button", { name: button }).click();
  await settle(page);
};
await zoom(5, "Zoom in");
await shot("02-explore-close");
await page.getByRole("button", { name: "Reset view" }).click();
await zoom(3, "Zoom out");
await shot("03-explore-far");
await page.getByRole("button", { name: "Reset view" }).click();
await page.getByRole("button", { name: "Rotate right (E)" }).click();
await settle(page);
await shot("04-explore-rotated");
await page.getByRole("button", { name: "Reset view" }).click();
await settle(page);
await page.locator('.roster-panel .agent-row[data-agent="cleo"]').click();
await settle(page, 3500);
await shot("05-follow-cleo");
await page.keyboard.press("Escape");
await page.getByRole("button", { name: "Dashboard" }).click();
await settle(page);
await shot("06-dashboard");

notes.capturedAt = new Date().toISOString();
writeFileSync(join(dir, "notes.json"), JSON.stringify(notes, null, 2));
console.log(JSON.stringify(notes, null, 2));
await browser.close();
