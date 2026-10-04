import { afterEach, describe, expect, it, vi } from "vitest";
import { createLiveSource, toSnapshot, type EventSourceLike } from "../../src/live/live-source";
import type { LiveAgent, LiveState, LiveTeam } from "../../src/live/types";

const NOW = 10_000;

const team = (id: string, project: string, host = "claude", accent = "#e4572e"): LiveTeam => ({
  id,
  project,
  host,
  accent,
  lastEventAt: NOW,
});

const agent = (id: string, teamId: string, project: string, over: Partial<LiveAgent> = {}): LiveAgent => ({
  id,
  teamId,
  kind: "subagent",
  role: "implementer",
  name: id.toUpperCase(),
  label: `Task of ${id}`,
  action: "edit-code",
  status: "working",
  host: "claude",
  project,
  startedAt: NOW - 600,
  lastEventAt: NOW - 1,
  statusSince: NOW - 1,
  ...over,
});

function state(teams: LiveTeam[], agents: LiveAgent[]): LiveState {
  return {
    teams: Object.fromEntries(teams.map((t) => [t.id, t])),
    agents: Object.fromEntries(agents.map((a) => [a.id, a])),
    pendingSpawns: [],
    ended: {},
    finishedRuns: {},
  };
}

describe("toSnapshot", () => {
  it("maps statuses, roles and the agent fields the HUD shows", () => {
    const s = state(
      [team("t1", "alpha", "codex", "#17bebb")],
      [
        agent("a1", "t1", "alpha", { kind: "coordinator", role: "coordinator", status: "ready", host: "codex" }),
        agent("a2", "t1", "alpha", { status: "attention", role: "reviewer", action: "read" }),
        agent("a3", "t1", "alpha", { status: "done", finishedAt: NOW - 240 }),
        agent("a4", "t1", "alpha", { status: "uncertain" }),
        agent("a5", "t1", "alpha", { status: "working", role: "tester", action: "run-tests", label: "Run the suite" }),
      ],
    );
    const snap = toSnapshot(s, NOW);
    const byId = Object.fromEntries(snap.agents.map((a) => [a.id, a]));
    expect(byId.a1).toMatchObject({ status: "ready", kind: "coordinator", role: "coordinator", host: "codex", teamId: "t1", project: "alpha", provider: "Codex" });
    expect(byId.a2).toMatchObject({ status: "issue", role: "reviewer", action: "read" });
    expect(byId.a3.status).toBe("done");
    expect(byId.a4.status).toBe("uncertain");
    expect(byId.a5).toMatchObject({ status: "working", role: "tester", action: "run-tests", task: "Run the suite", name: "A5" });
    expect(byId.a5.look.accent).toBe("#17bebb");
    expect(snap.scenarioId).toBe("live");
    expect(snap.completedThisSession).toBe(1);
  });

  it("derives elapsed minutes from startedAt", () => {
    const s = state(
      [team("t1", "alpha")],
      [
        agent("w", "t1", "alpha", { startedAt: NOW - 125 }),
        agent("r", "t1", "alpha", { status: "ready", kind: "coordinator", role: "coordinator" }),
        agent("d", "t1", "alpha", { status: "done", startedAt: NOW - 900, finishedAt: NOW - 300 }),
      ],
    );
    const byId = Object.fromEntries(toSnapshot(s, NOW).agents.map((a) => [a.id, a]));
    expect(byId.w.elapsedMinutes).toBe(2);
    expect(byId.r.elapsedMinutes).toBeNull();
    expect(byId.d.elapsedMinutes).toBe(10);
  });

  it("copies startedAt, converted from seconds to milliseconds", () => {
    const s = state([team("t1", "alpha")], [agent("w", "t1", "alpha", { startedAt: NOW - 125 })]);
    expect(toSnapshot(s, NOW).agents[0].startedAt).toBe((NOW - 125) * 1000);
  });

  it("applies the cap with priority attention, working, then newest, and counts overflow per project", () => {
    const agents = [
      agent("old-ready", "t1", "alpha", { status: "ready", startedAt: 1 }),
      agent("new-ready", "t1", "alpha", { status: "ready", startedAt: 900 }),
      agent("mid-done", "t2", "beta", { status: "done", startedAt: 500 }),
      agent("work-old", "t1", "alpha", { status: "working", startedAt: 10 }),
      agent("work-new", "t2", "beta", { status: "working", startedAt: 800 }),
      agent("warn", "t2", "beta", { status: "attention", startedAt: 5 }),
    ];
    const s = state([team("t1", "alpha"), team("t2", "beta")], agents);
    const snap = toSnapshot(s, NOW, 4);
    expect(snap.agents.map((a) => a.id).sort()).toEqual(["new-ready", "warn", "work-new", "work-old"]);
    expect(snap.overflow).toEqual({ alpha: 1, beta: 1 });
    expect(toSnapshot(s, NOW, 32).overflow).toEqual({});
  });

  it("lists teams in a stable order with the visible count", () => {
    const s = state(
      [team("z", "alpha"), team("a", "alpha"), team("m", "aaa")],
      [agent("1", "z", "alpha"), agent("2", "a", "alpha"), agent("3", "a", "alpha"), agent("4", "m", "aaa")],
    );
    const teams = toSnapshot(s, NOW).teams;
    expect(teams.map((t) => t.id)).toEqual(["m", "a", "z"]);
    expect(teams.map((t) => t.count)).toEqual([1, 2, 1]);
    expect(teams[0]).toMatchObject({ project: "aaa", host: "claude", accent: "#e4572e" });
  });

  it("is pure: it does not mutate its input and repeats its output", () => {
    const s = state([team("t1", "alpha")], [agent("a", "t1", "alpha"), agent("b", "t1", "alpha", { status: "attention" })]);
    const before = structuredClone(s);
    const first = toSnapshot(s, NOW, 1);
    expect(s).toEqual(before);
    expect(toSnapshot(s, NOW, 1)).toEqual(first);
  });

  it("ignores an unsafe team accent", () => {
    const s = state([team("t1", "alpha", "claude", "red;background:url(x)")], [agent("a", "t1", "alpha")]);
    const snap = toSnapshot(s, NOW);
    expect(snap.teams[0].accent).toMatch(/^#[0-9a-f]{6}$/i);
    expect(snap.agents[0].look.accent).toBe(snap.teams[0].accent);
  });
});

class FakeEventSource implements EventSourceLike {
  static instances: FakeEventSource[] = [];
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  closed = false;
  constructor(public url: string) {
    FakeEventSource.instances.push(this);
  }
  close() {
    this.closed = true;
  }
  emit(payload: unknown) {
    this.onmessage?.({ data: typeof payload === "string" ? payload : JSON.stringify(payload) } as MessageEvent);
  }
}

const message = (enabled: boolean, s: LiveState) => ({ enabled, state: s });

describe("createLiveSource", () => {
  afterEach(() => {
    FakeEventSource.instances = [];
    vi.useRealTimers();
  });

  const make = (now = () => NOW) =>
    createLiveSource("/api/world/stream", { eventSource: FakeEventSource, now });

  it("opens the stream and starts empty and disabled", () => {
    const source = make();
    expect(FakeEventSource.instances[0].url).toBe("/api/world/stream");
    expect(source.current().agents).toEqual([]);
    expect(source.enabled()).toBe(false);
  });

  it("updates current() and notifies on each message", () => {
    const source = make();
    const fn = vi.fn();
    source.subscribe(fn);
    FakeEventSource.instances[0].emit(message(true, state([team("t1", "alpha")], [agent("a", "t1", "alpha")])));
    expect(source.enabled()).toBe(true);
    expect(source.current().agents.map((a) => a.id)).toEqual(["a"]);
    expect(fn).toHaveBeenCalledTimes(1);
    expect(fn.mock.calls[0][0]).toBe(source.current());
  });

  it("enabled() follows the last snapshot", () => {
    const source = make();
    const es = FakeEventSource.instances[0];
    es.emit(message(true, state([], [])));
    es.emit(message(false, state([], [])));
    expect(source.enabled()).toBe(false);
  });

  it("ignores malformed messages and keeps the last snapshot", () => {
    const source = make();
    const es = FakeEventSource.instances[0];
    es.emit(message(true, state([team("t1", "alpha")], [agent("a", "t1", "alpha")])));
    const kept = source.current();
    const fn = vi.fn();
    source.subscribe(fn);
    es.emit("not json");
    es.emit({ enabled: true });
    expect(source.current()).toBe(kept);
    expect(source.enabled()).toBe(true);
    expect(fn).not.toHaveBeenCalled();
  });

  describe("when the stream drops", () => {
    const live = () => {
      vi.useFakeTimers();
      const source = make();
      const es = FakeEventSource.instances[0];
      es.emit(message(true, state([team("t1", "alpha")], [agent("a", "t1", "alpha"), agent("b", "t1", "alpha", { status: "attention" })])));
      return { source, es };
    };

    it("is connected until an error, then marks every agent uncertain and says so", () => {
      const { source, es } = live();
      expect(source.connected()).toBe(true);
      const fn = vi.fn();
      source.subscribe(fn);
      es.onerror?.({} as Event);
      expect(source.connected()).toBe(false);
      expect(source.current().agents.map((a) => a.status)).toEqual(["uncertain", "uncertain"]);
      expect(source.current().agents.map((a) => a.id).sort()).toEqual(["a", "b"]);
      expect(source.enabled()).toBe(true);
      expect(fn).toHaveBeenCalledTimes(1);
      es.onerror?.({} as Event); // a second error from the same stream does not notify again
      expect(fn).toHaveBeenCalledTimes(1);
      source.stop();
    });

    it("reconnects after 1 s, doubling to a 30 s cap", () => {
      const { source, es } = live();
      es.onerror?.({} as Event);
      expect(es.closed).toBe(true);
      expect(FakeEventSource.instances).toHaveLength(1);
      vi.advanceTimersByTime(999);
      expect(FakeEventSource.instances).toHaveLength(1);
      vi.advanceTimersByTime(1);
      expect(FakeEventSource.instances).toHaveLength(2);
      expect(FakeEventSource.instances[1].url).toBe("/api/world/stream");
      const waits: number[] = [];
      for (let i = 1; i <= 6; i++) {
        FakeEventSource.instances[i].onerror?.({} as Event);
        const before = FakeEventSource.instances.length;
        let waited = 0;
        while (FakeEventSource.instances.length === before) {
          vi.advanceTimersByTime(500);
          waited += 500;
        }
        waits.push(waited);
      }
      expect(waits).toEqual([2000, 4000, 8000, 16000, 30000, 30000]);
      source.stop();
    });

    it("replaces the state on the next message and resets the backoff", () => {
      const { source, es } = live();
      es.onerror?.({} as Event);
      vi.advanceTimersByTime(1000);
      FakeEventSource.instances[1].onerror?.({} as Event);
      vi.advanceTimersByTime(2000);
      const fn = vi.fn();
      source.subscribe(fn);
      FakeEventSource.instances[2].emit(message(true, state([team("t2", "beta")], [agent("c", "t2", "beta")])));
      expect(source.connected()).toBe(true);
      expect(source.current().agents.map((a) => [a.id, a.status])).toEqual([["c", "working"]]);
      expect(fn).toHaveBeenCalledTimes(1);
      FakeEventSource.instances[2].onerror?.({} as Event);
      vi.advanceTimersByTime(1000);
      expect(FakeEventSource.instances).toHaveLength(4);
      source.stop();
    });

    it("stop() cancels a pending reconnect", () => {
      const { source, es } = live();
      es.onerror?.({} as Event);
      source.stop();
      vi.advanceTimersByTime(60_000);
      expect(FakeEventSource.instances).toHaveLength(1);
    });

    it("does not tick elapsed times while disconnected", () => {
      vi.useFakeTimers();
      let now = NOW;
      const source = make(() => now);
      const es = FakeEventSource.instances[0];
      es.emit(message(true, state([team("t1", "alpha")], [agent("a", "t1", "alpha", { startedAt: NOW })])));
      es.onerror?.({} as Event);
      const fn = vi.fn();
      source.subscribe(fn);
      now = NOW + 600;
      vi.advanceTimersByTime(30_000);
      expect(fn).not.toHaveBeenCalled();
      expect(source.current().agents[0].elapsedMinutes).toBe(0);
      source.stop();
    });
  });

  it("advance() does nothing", () => {
    const source = make();
    const fn = vi.fn();
    source.subscribe(fn);
    source.advance();
    expect(fn).not.toHaveBeenCalled();
  });

  it("stop() closes the stream and silences subscribers", () => {
    const source = make();
    const es = FakeEventSource.instances[0];
    const fn = vi.fn();
    source.subscribe(fn);
    source.stop();
    expect(es.closed).toBe(true);
    es.emit(message(true, state([], [])));
    expect(fn).not.toHaveBeenCalled();
  });

  it("an unsubscribed listener is not called", () => {
    const source = make();
    const fn = vi.fn();
    const off = source.subscribe(fn);
    off();
    FakeEventSource.instances[0].emit(message(true, state([], [])));
    expect(fn).not.toHaveBeenCalled();
  });

  it("counts every agent it has seen finish as completed this session", () => {
    const source = make();
    const es = FakeEventSource.instances[0];
    const t = team("t1", "alpha");
    es.emit(message(true, state([t], [agent("a", "t1", "alpha", { status: "done" })])));
    es.emit(message(true, state([t], [agent("b", "t1", "alpha", { status: "done" })])));
    es.emit(message(true, state([t], [])));
    expect(source.current().completedThisSession).toBe(2);
  });

  it("refreshes elapsed time on a timer without a new message", () => {
    vi.useFakeTimers();
    let now = NOW;
    const source = make(() => now);
    FakeEventSource.instances[0].emit(message(true, state([team("t1", "alpha")], [agent("a", "t1", "alpha", { startedAt: NOW })])));
    expect(source.current().agents[0].elapsedMinutes).toBe(0);
    const fn = vi.fn();
    source.subscribe(fn);
    now = NOW + 180;
    vi.advanceTimersByTime(30_000);
    expect(source.current().agents[0].elapsedMinutes).toBe(3);
    expect(fn).toHaveBeenCalledTimes(1);
    vi.advanceTimersByTime(30_000);
    expect(fn).toHaveBeenCalledTimes(1);
    source.stop();
  });

  it("starts from an initial snapshot when given one", () => {
    const source = createLiveSource("/x", {
      eventSource: FakeEventSource,
      now: () => NOW,
      initial: message(true, state([team("t1", "alpha")], [agent("a", "t1", "alpha")])),
    });
    expect(source.enabled()).toBe(true);
    expect(source.current().agents).toHaveLength(1);
  });
});
