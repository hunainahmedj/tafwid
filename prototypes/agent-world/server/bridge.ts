// Bridge between the Tafwid activity log and the dashboard. Read-only: it
// tails the hook's event logs, projects delegated run records, folds both
// into a LiveState and serves it over GET /api/world/snapshot and
// GET /api/world/stream (server-sent events). Nothing here writes to the
// state directory.
import { createHmac } from "node:crypto";
import { existsSync, lstatSync, readFileSync, readdirSync } from "node:fs";
import type { IncomingMessage, ServerResponse } from "node:http";
import { homedir } from "node:os";
import { basename, join } from "node:path";
import type { Plugin } from "vite";
import { emptyLiveState, fold, tick } from "../src/live/fold";
import type { EventHost, LiveState, Role, RunEvent, WorldEvent } from "../src/live/types";
import { createTailer } from "./tail";

export interface Snapshot {
  enabled: boolean;
  state: LiveState;
}

const SALT_BYTES = 32;
const POLL_MS = 1000;
const PUSH_MS = 250;
const HEARTBEAT_MS = 15_000;
const RUN_WINDOW_S = 120;
const STALE_RUN_S = 15;
const LABEL_CHARS = 80;
const TITLE_SOURCE_CHARS = 2000;
const ACTIVE = new Set(["starting", "running"]);
const ROLES: ReadonlySet<string> = new Set<Role>([
  "coordinator",
  "implementer",
  "reviewer",
  "documenter",
  "researcher",
  "tester",
]);
const ROLE_TAG = /\[role:\s*([A-Za-z-]*)\s*\]/gi;

/** Same pseudonym as the Python hook: hmac_sha256(salt, raw) as hex, first 16. */
export function hashId(salt: Buffer, raw: string): string {
  return createHmac("sha256", salt).update(String(raw)).digest("hex").slice(0, 16);
}

function str(value: unknown): string | null {
  return typeof value === "string" && value !== "" ? value : null;
}

function projectRun(
  record: Record<string, unknown>,
  salt: Buffer,
  now: number,
): RunEvent | null {
  const id = str(record.id);
  const owner = str(record.coordinator_task_id) ?? str(record.codex_thread_id);
  if (!id || !owner) return null;

  const rawStatus = typeof record.status === "string" ? record.status : "";
  const updatedAt = typeof record.updated_at === "number" ? record.updated_at : 0;
  const endedAt = typeof record.ended_at === "number" ? record.ended_at : 0;
  const active = ACTIVE.has(rawStatus);
  const stale = active && now - updatedAt > STALE_RUN_S;

  // Active and still reporting, or finished (or gone quiet) within two minutes.
  const live = active && !stale;
  if (!live && now - Math.max(updatedAt, endedAt) > RUN_WINDOW_S) return null;

  let status: RunEvent["status"];
  if (live) status = "working";
  else if (rawStatus === "completed") status = "done";
  else status = "attention"; // stale launcher, blocked, needs_review, error, interrupted, timeout...

  const title = typeof record.title === "string" ? record.title.slice(0, TITLE_SOURCE_CHARS) : "";
  let role: Role | null = null;
  for (const [, name] of title.matchAll(ROLE_TAG)) {
    if (ROLES.has(name.toLowerCase())) role = name.toLowerCase() as Role;
  }
  const label = title.replace(ROLE_TAG, " ").split(/\s+/).filter(Boolean).join(" ").slice(0, LABEL_CHARS);

  const cwd = str(record.cwd);
  const host: EventHost =
    record.coordinator_host === "claude" || record.coordinator_host === "codex"
      ? record.coordinator_host
      : "unknown";

  return {
    v: 1,
    t: now,
    event: "run",
    session: hashId(salt, owner),
    project: cwd ? basename(cwd) || null : null,
    host,
    run: hashId(salt, id),
    label: label || null,
    role,
    status,
  };
}

/**
 * Project the run records under `<stateDir>/workers` into run events, one per
 * included run, stamped `now` so a long-running run is never silent. Lock
 * files, unreadable files and records without an id or owner are ignored.
 */
export function readRuns(
  stateDir: string,
  salt: Buffer,
  now: number = Date.now() / 1000,
): WorldEvent[] {
  const dir = join(stateDir, "workers");
  let names: string[];
  try {
    names = readdirSync(dir).filter((name) => name.endsWith(".json"));
  } catch {
    return [];
  }
  const events: WorldEvent[] = [];
  for (const name of names.sort()) {
    try {
      const path = join(dir, name);
      if (!lstatSync(path).isFile()) continue;
      const record: unknown = JSON.parse(readFileSync(path, "utf8"));
      if (typeof record !== "object" || record === null || Array.isArray(record)) continue;
      const event = projectRun(record as Record<string, unknown>, salt, now);
      if (event) events.push(event);
    } catch {
      // A record being rewritten or damaged must not stop the others.
    }
  }
  return events;
}

export function resolveHome(home?: string): string {
  return home ?? (process.env.TAFWID_HOME || join(homedir(), ".tafwid"));
}

type Next = (error?: unknown) => void;

export interface World {
  poll(): void;
  snapshot(): Snapshot;
  handler(req: IncomingMessage, res: ServerResponse, next: Next): void;
  /** Begin the 1 s poll loop (does an immediate first poll). */
  start(): void;
  /** Stop the poll loop and close every open stream. */
  stop(): void;
}

interface Client {
  res: ServerResponse;
  lastData: string;
  lastWrite: number;
}

export function createWorld(
  home: string,
  clock: () => number = () => Date.now() / 1000,
): World {
  const stateDir = join(home, "state");
  const worldDir = join(stateDir, "world");
  const tailer = createTailer(worldDir);
  let state = emptyLiveState();
  let salt: Buffer | null = null;
  let pollTimer: NodeJS.Timeout | undefined;
  let pushTimer: NodeJS.Timeout | undefined;
  const clients = new Set<Client>();

  function loadSalt(): Buffer | null {
    if (salt) return salt;
    try {
      const bytes = readFileSync(join(worldDir, "salt"));
      if (bytes.length === SALT_BYTES) salt = bytes;
    } catch {
      // No salt yet: the hook has not run, so there are no run owners to join.
    }
    return salt;
  }

  function apply(events: WorldEvent[]) {
    for (const event of events) {
      try {
        state = fold(state, event);
      } catch (error) {
        console.warn("[world] skipped an event the reducer rejected:", error);
      }
    }
  }

  function poll() {
    try {
      apply(tailer.poll());
    } catch (error) {
      console.warn("[world] log read failed:", error);
    }
    try {
      const key = loadSalt();
      if (key) apply(readRuns(stateDir, key, clock()));
    } catch (error) {
      console.warn("[world] run read failed:", error);
    }
    try {
      state = tick(state, clock());
    } catch (error) {
      console.warn("[world] tick failed:", error);
    }
  }

  function snapshot(): Snapshot {
    return { enabled: existsSync(join(worldDir, "enabled")), state };
  }

  function flush() {
    if (clients.size === 0) return;
    const data = JSON.stringify(snapshot());
    const now = Date.now();
    for (const client of clients) {
      try {
        if (data !== client.lastData) {
          client.res.write(`data: ${data}\n\n`);
          client.lastData = data;
          client.lastWrite = now;
        } else if (now - client.lastWrite >= HEARTBEAT_MS) {
          client.res.write(": heartbeat\n\n");
          client.lastWrite = now;
        }
      } catch {
        clients.delete(client);
      }
    }
  }

  function handler(req: IncomingMessage, res: ServerResponse, next: Next) {
    const path = (req.url ?? "").split("?")[0];
    if (path !== "/api/world/snapshot" && path !== "/api/world/stream") {
      next();
      return;
    }
    if (req.method !== "GET") {
      res.statusCode = 405;
      res.setHeader("Allow", "GET");
      res.end();
      return;
    }
    poll();
    if (path === "/api/world/snapshot") {
      res.setHeader("Content-Type", "application/json");
      res.setHeader("Cache-Control", "no-store");
      res.end(JSON.stringify(snapshot()));
      return;
    }
    res.writeHead(200, {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-store",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    });
    const data = JSON.stringify(snapshot());
    res.write(`data: ${data}\n\n`);
    const client: Client = { res, lastData: data, lastWrite: Date.now() };
    clients.add(client);
    pushTimer ??= setInterval(flush, PUSH_MS);
    pushTimer.unref();
    req.on("close", () => {
      clients.delete(client);
      if (clients.size === 0 && pushTimer) {
        clearInterval(pushTimer);
        pushTimer = undefined;
      }
    });
  }

  return {
    poll,
    snapshot,
    handler,
    start() {
      if (pollTimer) return;
      poll();
      pollTimer = setInterval(poll, POLL_MS);
      pollTimer.unref();
    },
    stop() {
      if (pollTimer) clearInterval(pollTimer);
      pollTimer = undefined;
      if (pushTimer) clearInterval(pushTimer);
      pushTimer = undefined;
      for (const client of clients) client.res.end();
      clients.clear();
    },
  };
}

/** Vite plugin serving the world endpoints in both dev and preview. */
export function worldBridge(options: { home?: string } = {}): Plugin {
  const world = createWorld(resolveHome(options.home));
  const attach = (server: {
    middlewares: { use: (fn: (req: IncomingMessage, res: ServerResponse, next: Next) => void) => unknown };
    httpServer: { once: (event: "close", fn: () => void) => unknown } | null;
  }) => {
    server.middlewares.use((req, res, next) => world.handler(req, res, next));
    world.start();
    server.httpServer?.once("close", () => world.stop());
  };
  return {
    name: "tafwid-world-bridge",
    configureServer: attach,
    configurePreviewServer: attach,
  };
}
