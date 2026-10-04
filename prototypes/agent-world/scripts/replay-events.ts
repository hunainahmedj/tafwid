// Replays a fixture of activity-log lines into a Tafwid home, so the dashboard
// bridge can be exercised without a real session. Fixture lines carry `dt`
// (seconds from now; negative for the past) instead of an absolute `t`; the
// replay writes `t = now + dt`, the way the plugin's hook stamps its lines.
//
// Library use (the e2e tests):  replay(home, lines)  appendEvents(home, lines)
// CLI (writes only under the home you name; it never defaults to ~/.tafwid):
//   tsx scripts/replay-events.ts --home <dir> [--fixture <file>] [--enable]
import { appendFileSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { dayStamp } from "../server/tail";
import type { HookEvent } from "../src/live/types";

/** One fixture line: a hook event whose `t` is replaced by `dt`. Unset fields take the hook's null defaults. */
export type ReplayLine = Pick<HookEvent, "session" | "event"> &
  Partial<Omit<HookEvent, "t" | "session" | "event">> & { dt: number };

/** The folder the bridge tails, and holds the on/off marker. */
export const worldDir = (home: string) => join(home, "state", "world");

/** Today's log file by local date, the name the bridge looks for. */
export const logPath = (home: string, now = Date.now() / 1000) =>
  join(worldDir(home), `events-${dayStamp(new Date(now * 1000))}.jsonl`);

function toLine({ dt, ...rest }: ReplayLine, now: number): string {
  const event: HookEvent = {
    v: 1,
    t: Math.round((now + dt) * 1000) / 1000,
    host: "claude",
    project: null,
    agent: null,
    phase: null,
    agentType: null,
    label: null,
    action: null,
    role: null,
    status: null,
    ...rest,
  };
  return `${JSON.stringify(event)}\n`;
}

/** Reads a fixture file: one JSON object per line, each with a numeric `dt`. */
export function parseFixture(text: string): ReplayLine[] {
  const lines: ReplayLine[] = [];
  text.split("\n").forEach((raw, index) => {
    if (!raw.trim()) return;
    let parsed: unknown;
    try {
      parsed = JSON.parse(raw);
    } catch {
      throw new Error(`fixture line ${index + 1} is not JSON`);
    }
    const line = parsed as Partial<ReplayLine> | null;
    if (typeof line !== "object" || line === null || typeof line.dt !== "number" || !line.session || !line.event) {
      throw new Error(`fixture line ${index + 1} needs numeric dt, session and event`);
    }
    lines.push(line as ReplayLine);
  });
  return lines;
}

/** Starts today's log afresh with `lines`. Returns the file written. */
export function replay(home: string, lines: ReplayLine[], now = Date.now() / 1000): string {
  mkdirSync(worldDir(home), { recursive: true });
  const path = logPath(home, now);
  writeFileSync(path, lines.map((line) => toLine(line, now)).join(""));
  return path;
}

/** Adds `lines` to today's log, as the hook does while a session runs. Returns the file written. */
export function appendEvents(home: string, lines: ReplayLine[], now = Date.now() / 1000): string {
  mkdirSync(worldDir(home), { recursive: true });
  const path = logPath(home, now);
  appendFileSync(path, lines.map((line) => toLine(line, now)).join(""));
  return path;
}

/** Turns the world switch on or off by creating or removing the marker file. */
export function setEnabled(home: string, on: boolean): void {
  const marker = join(worldDir(home), "enabled");
  if (on) {
    mkdirSync(worldDir(home), { recursive: true });
    writeFileSync(marker, "");
  } else rmSync(marker, { force: true });
}

function cli(argv: string[]): void {
  const flag = (name: string) => {
    const at = argv.indexOf(name);
    return at < 0 ? undefined : argv[at + 1];
  };
  const home = flag("--home");
  if (!home) throw new Error("usage: replay-events.ts --home <dir> [--fixture <file>] [--enable]");
  const fixture = flag("--fixture") ?? fileURLToPath(new URL("../tests/e2e/fixtures/events-sample.replay", import.meta.url));
  const lines = parseFixture(readFileSync(resolve(fixture), "utf8"));
  const path = replay(resolve(home), lines);
  if (argv.includes("--enable")) setEnabled(resolve(home), true);
  console.log(`replayed ${lines.length} events into ${path}`);
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    cli(process.argv.slice(2));
  } catch (error) {
    console.error((error as Error).message);
    process.exitCode = 1;
  }
}
