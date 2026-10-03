// Validates every built environment package against the runtime contract.
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { validateManifest } from "../src/contract/validate.ts";

const BUDGET_MB = { kit: 10, baked: 25 } as const;
const root = new URL("../public/environments/", import.meta.url).pathname;
let failed = false;
let found = 0;

const dirSize = (dir: string): number =>
  readdirSync(dir).reduce((sum, name) => {
    const p = join(dir, name);
    return sum + (statSync(p).isDirectory() ? dirSize(p) : statSync(p).size);
  }, 0);

for (const env of existsSync(root) ? readdirSync(root) : []) {
  const envDir = join(root, env);
  if (!statSync(envDir).isDirectory()) continue;
  for (const variant of readdirSync(envDir)) {
    const dir = join(envDir, variant);
    const manifestPath = join(dir, "manifest.json");
    if (!existsSync(manifestPath)) continue;
    found++;
    const result = validateManifest(JSON.parse(readFileSync(manifestPath, "utf8")));
    const label = `${env}/${variant}`;
    if (!result.ok) {
      failed = true;
      console.error(`FAIL ${label}\n  ${result.errors.join("\n  ")}`);
      continue;
    }
    const scene = join(dir, result.manifest.scene);
    if (!existsSync(scene)) {
      failed = true;
      console.error(`FAIL ${label}: missing ${result.manifest.scene}`);
      continue;
    }
    const mb = dirSize(dir) / 1024 / 1024;
    const budget = BUDGET_MB[result.manifest.variant];
    if (mb > budget) {
      failed = true;
      console.error(`FAIL ${label}: ${mb.toFixed(1)} MB exceeds the ${budget} MB budget`);
      continue;
    }
    console.log(`OK ${label} ${mb.toFixed(1)} MB`);
  }
}
if (!found) console.log("No packages found under public/environments/.");
process.exit(failed ? 1 : 0);
