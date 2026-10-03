// @vitest-environment node
import {
  appendFileSync,
  mkdirSync,
  mkdtempSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import http from "node:http";
import type { AddressInfo } from "node:net";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { createWorld, hashId, readRuns } from "../../server/bridge";
import { createTailer } from "../../server/tail";
import type { HookEvent, RunEvent } from "../../src/live/types";

const ZERO_SALT = Buffer.alloc(32);
const NOW = 2_000_000;

let home: string;
beforeEach(() => {
  home = mkdtempSync(join(tmpdir(), "world-bridge-"));
});
afterEach(() => {
  rmSync(home, { recursive: true, force: true });
});

function hook(over: Partial<HookEvent> = {}): HookEvent {
  return {
    v: 1,
    t: NOW,
    host: "claude",
    session: "aaaaaaaaaaaaaaaa",
    project: "tafwid",
    agent: null,
    event: "prompt",
    phase: null,
    agentType: null,
    label: null,
    action: null,
    role: null,
    status: null,
    ...over,
  };
}

const line = (event: object) => JSON.stringify(event) + "\n";

describe("hashId", () => {
  it("matches the Python hash_id shared vector", () => {
    expect(hashId(ZERO_SALT, "abc")).toBe("fd7adb152c05ef80");
  });
});

describe("createTailer", () => {
  let dir: string;
  beforeEach(() => {
    dir = join(home, "state", "world");
    mkdirSync(dir, { recursive: true });
  });
  const day = (d: string) => join(dir, `events-${d}.jsonl`);
  const at = (iso: string) => () => new Date(iso);

  it("returns only complete lines and resumes at its offset", () => {
    const tailer = createTailer(dir, at("2026-10-03T12:00:00"));
    writeFileSync(day("2026-10-03"), line(hook({ t: 1 })) + line(hook({ t: 2 })));
    expect(tailer.poll().map((e) => e.t)).toEqual([1, 2]);
    expect(tailer.poll()).toEqual([]);
    appendFileSync(day("2026-10-03"), line(hook({ t: 3 })));
    expect(tailer.poll().map((e) => e.t)).toEqual([3]);
  });

  it("holds a partial last line back until its newline arrives", () => {
    const tailer = createTailer(dir, at("2026-10-03T12:00:00"));
    const text = line(hook({ t: 7, label: "héllo wörld" }));
    const cut = Buffer.byteLength(text) - 12;
    const bytes = Buffer.from(text);
    writeFileSync(day("2026-10-03"), line(hook({ t: 1 })));
    appendFileSync(day("2026-10-03"), bytes.subarray(0, cut));
    expect(tailer.poll().map((e) => e.t)).toEqual([1]);
    expect(tailer.poll()).toEqual([]);
    appendFileSync(day("2026-10-03"), bytes.subarray(cut));
    const got = tailer.poll();
    expect(got.map((e) => e.t)).toEqual([7]);
    expect((got[0] as HookEvent).label).toBe("héllo wörld");
  });

  it("reads yesterday's file first, then today's, from offset 0 on start", () => {
    writeFileSync(day("2026-10-02"), line(hook({ t: 1 })));
    writeFileSync(day("2026-10-03"), line(hook({ t: 2 })));
    writeFileSync(day("2026-09-30"), line(hook({ t: 99 })));
    const tailer = createTailer(dir, at("2026-10-03T00:00:05"));
    expect(tailer.poll().map((e) => e.t)).toEqual([1, 2]);
  });

  it("continues in the new file after a date rollover", () => {
    let current = new Date("2026-10-03T23:59:59");
    const tailer = createTailer(dir, () => current);
    writeFileSync(day("2026-10-03"), line(hook({ t: 1 })));
    expect(tailer.poll().map((e) => e.t)).toEqual([1]);
    // The old day's file still gets a late line; the new day's file begins.
    current = new Date("2026-10-04T00:00:01");
    appendFileSync(day("2026-10-03"), line(hook({ t: 2 })));
    writeFileSync(day("2026-10-04"), line(hook({ t: 3 })));
    expect(tailer.poll().map((e) => e.t)).toEqual([2, 3]);
    appendFileSync(day("2026-10-04"), line(hook({ t: 4 })));
    expect(tailer.poll().map((e) => e.t)).toEqual([4]);
  });

  it("skips and counts malformed lines without throwing", () => {
    const tailer = createTailer(dir, at("2026-10-03T12:00:00"));
    writeFileSync(
      day("2026-10-03"),
      line(hook({ t: 1 })) +
        "{not json\n" +
        "[1,2]\n" +
        '{"v":1,"t":"x","event":"prompt"}\n' +
        line({ v: 1, t: 5, event: "run" }) +
        "\n" +
        line(hook({ t: 2 })),
    );
    expect(tailer.poll().map((e) => e.t)).toEqual([1, 2]);
    expect(tailer.malformed()).toBe(4); // the blank line is not counted
  });

  it("restarts a file that was truncated", () => {
    const tailer = createTailer(dir, at("2026-10-03T12:00:00"));
    writeFileSync(day("2026-10-03"), line(hook({ t: 1 })) + line(hook({ t: 2 })));
    tailer.poll();
    writeFileSync(day("2026-10-03"), line(hook({ t: 3 })));
    expect(tailer.poll().map((e) => e.t)).toEqual([3]);
  });

  it("returns nothing when the directory does not exist", () => {
    const tailer = createTailer(join(home, "missing"), at("2026-10-03T12:00:00"));
    expect(tailer.poll()).toEqual([]);
  });
});

describe("readRuns", () => {
  const stateDir = () => join(home, "state");
  function writeRun(id: string, over: Record<string, unknown> = {}, name = id + ".json") {
    const dir = join(stateDir(), "workers");
    mkdirSync(dir, { recursive: true });
    const record = {
      id,
      title: "Implement the bridge",
      status: "running",
      coordinator_task_id: "abc",
      coordinator_host: "claude",
      cwd: "/work/private-dir/tafwid",
      started_at: NOW - 60,
      updated_at: NOW - 1,
      ended_at: null,
      ...over,
    };
    writeFileSync(join(dir, name), JSON.stringify(record));
  }
  const ID1 = "11111111-1111-4111-8111-111111111111";
  const ID2 = "22222222-2222-4222-8222-222222222222";

  it("projects a run with hashed ids and only the project basename", () => {
    writeRun(ID1);
    const [run] = readRuns(stateDir(), ZERO_SALT, NOW) as RunEvent[];
    expect(run).toEqual({
      v: 1,
      t: NOW,
      event: "run",
      session: "fd7adb152c05ef80",
      project: "tafwid",
      host: "claude",
      run: hashId(ZERO_SALT, ID1),
      label: "Implement the bridge",
      role: null,
      status: "working",
    });
    expect(JSON.stringify(run)).not.toContain("private-dir");
    expect(JSON.stringify(run)).not.toContain(ID1);
  });

  it("reads the legacy codex_thread_id owner and an unknown host", () => {
    writeRun(ID1, { coordinator_task_id: undefined, coordinator_host: undefined, codex_thread_id: "abc" });
    const [run] = readRuns(stateDir(), ZERO_SALT, NOW) as RunEvent[];
    expect(run.session).toBe("fd7adb152c05ef80");
    expect(run.host).toBe("unknown");
  });

  it("lifts a role tag out of the title and trims the label to one line of 80", () => {
    writeRun(ID1, { title: "[role: Reviewer] Check\nthe   diff " + "x".repeat(200) });
    const [run] = readRuns(stateDir(), ZERO_SALT, NOW) as RunEvent[];
    expect(run.role).toBe("reviewer");
    expect(run.label).not.toContain("[role");
    expect(run.label).not.toContain("\n");
    expect(run.label!.length).toBeLessThanOrEqual(80);
    expect(run.label!.startsWith("Check the diff")).toBe(true);
  });

  it("maps statuses, including a stale heartbeat to attention", () => {
    const cases: Array<[string, number, RunEvent["status"]]> = [
      ["starting", 1, "working"],
      ["running", 1, "working"],
      ["running", 16, "attention"],
      ["starting", 16, "attention"],
      ["blocked", 1, "attention"],
      ["needs_review", 1, "attention"],
      ["error", 1, "attention"],
      ["interrupted", 1, "attention"],
    ];
    cases.forEach(([status, age, expected], i) => {
      writeRun(`00000000-0000-4000-8000-00000000000${i}`, {
        status,
        updated_at: NOW - age,
        ended_at: status === "running" || status === "starting" ? null : NOW - age,
      });
    });
    const runs = readRuns(stateDir(), ZERO_SALT, NOW) as RunEvent[];
    expect(runs).toHaveLength(cases.length);
    cases.forEach(([, , expected], i) => {
      const id = hashId(ZERO_SALT, `00000000-0000-4000-8000-00000000000${i}`);
      expect(runs.find((r) => r.run === id)!.status).toBe(expected);
    });
  });

  it("maps completed to done and drops runs that ended over two minutes ago", () => {
    writeRun(ID1, { status: "completed", ended_at: NOW - 30, updated_at: NOW - 30 });
    writeRun(ID2, { status: "completed", ended_at: NOW - 121, updated_at: NOW - 121 });
    const runs = readRuns(stateDir(), ZERO_SALT, NOW) as RunEvent[];
    expect(runs.map((r) => [r.run, r.status])).toEqual([[hashId(ZERO_SALT, ID1), "done"]]);
  });

  it("re-emits the current state with t = now on every read", () => {
    writeRun(ID1);
    const first = readRuns(stateDir(), ZERO_SALT, NOW) as RunEvent[];
    const later = readRuns(stateDir(), ZERO_SALT, NOW + 5) as RunEvent[];
    expect(first[0].t).toBe(NOW);
    expect(later[0].t).toBe(NOW + 5);
  });

  it("ignores lock files, unparseable files and records missing an id or owner", () => {
    writeRun(ID1);
    const dir = join(stateDir(), "workers");
    writeFileSync(join(dir, ID2 + ".json.lock"), "{}");
    writeFileSync(join(dir, "broken.json"), "{oops");
    writeFileSync(join(dir, "array.json"), "[]");
    writeRun("33333333-3333-4333-8333-333333333333", { coordinator_task_id: null });
    writeRun("", { id: undefined }, "noid.json");
    expect(readRuns(stateDir(), ZERO_SALT, NOW)).toHaveLength(1);
  });

  it("returns nothing when there is no workers directory", () => {
    expect(readRuns(stateDir(), ZERO_SALT, NOW)).toEqual([]);
  });
});

describe("world bridge endpoints", () => {
  let server: http.Server;
  let base: string;
  let world: ReturnType<typeof createWorld>;

  function markEnabled() {
    mkdirSync(join(home, "state", "world"), { recursive: true });
    writeFileSync(join(home, "state", "world", "enabled"), "");
  }
  const today = () => {
    const d = new Date();
    const p = (n: number) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
  };

  beforeEach(async () => {
    world = createWorld(home);
    server = http.createServer((req, res) =>
      world.handler(req, res, () => {
        res.statusCode = 404;
        res.end("next");
      }),
    );
    await new Promise<void>((r) => server.listen(0, "127.0.0.1", r));
    base = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
  });
  afterEach(async () => {
    world.stop();
    server.closeAllConnections();
    await new Promise<void>((r) => server.close(() => r()));
  });

  it("reports enabled: false when the marker is missing, and still serves state", async () => {
    const res = await fetch(`${base}/api/world/snapshot`);
    expect(res.status).toBe(200);
    expect(res.headers.get("content-type")).toContain("application/json");
    const body = await res.json();
    expect(body.enabled).toBe(false);
    expect(body.state).toEqual({ teams: {}, agents: {}, pendingSpawns: [], ended: {} });
  });

  it("reports enabled: true and folds events from today's log", async () => {
    markEnabled();
    const t = Date.now() / 1000;
    appendFileSync(
      join(home, "state", "world", `events-${today()}.jsonl`),
      line(hook({ t, session: "bbbbbbbbbbbbbbbb", event: "prompt" })),
    );
    const body = await (await fetch(`${base}/api/world/snapshot`)).json();
    expect(body.enabled).toBe(true);
    expect(Object.keys(body.state.teams)).toEqual(["bbbbbbbbbbbbbbbb"]);
  });

  it("answers anything but GET with 405", async () => {
    for (const method of ["POST", "PUT", "DELETE", "HEAD"]) {
      const res = await fetch(`${base}/api/world/snapshot`, { method });
      expect(res.status).toBe(405);
      expect(res.headers.get("allow")).toBe("GET");
    }
    expect((await fetch(`${base}/api/world/stream`, { method: "POST" })).status).toBe(405);
  });

  it("passes other paths on to the next handler", async () => {
    expect((await fetch(`${base}/index.html`)).status).toBe(404);
  });

  it("streams a snapshot on connect and again when the state changes", async () => {
    markEnabled();
    const res = await fetch(`${base}/api/world/stream`);
    expect(res.headers.get("content-type")).toContain("text/event-stream");
    const reader = res.body!.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    async function nextData(): Promise<{ enabled: boolean; state: { teams: object } }> {
      for (;;) {
        const idx = buffer.indexOf("\n\n");
        if (idx >= 0) {
          const block = buffer.slice(0, idx);
          buffer = buffer.slice(idx + 2);
          if (block.startsWith("data: ")) return JSON.parse(block.slice(6));
          continue;
        }
        const { value, done } = await reader.read();
        if (done) throw new Error("stream ended");
        buffer += decoder.decode(value, { stream: true });
      }
    }
    const first = await nextData();
    expect(first.enabled).toBe(true);
    expect(Object.keys(first.state.teams)).toEqual([]);

    appendFileSync(
      join(home, "state", "world", `events-${today()}.jsonl`),
      line(hook({ t: Date.now() / 1000, session: "cccccccccccccccc" })),
    );
    world.poll();
    const second = await nextData();
    expect(Object.keys(second.state.teams)).toEqual(["cccccccccccccccc"]);
    await reader.cancel();
  });
});
