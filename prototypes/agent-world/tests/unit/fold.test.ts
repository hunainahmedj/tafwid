import { describe, expect, it } from "vitest";
import {
  accentFor,
  emptyLiveState,
  fold,
  nameFor,
  tick,
} from "../../src/live/fold";
import type {
  HookEvent,
  LiveState,
  RunEvent,
  WorldEvent,
} from "../../src/live/types";

const T0 = 1_000_000;
const S = "aaaaaaaaaaaaaaaa";
const S2 = "bbbbbbbbbbbbbbbb";
const SUB1 = "1111111111111111";
const SUB2 = "2222222222222222";
const RUN = "9999999999999999";

function hook(over: Partial<HookEvent> & Pick<HookEvent, "event">): HookEvent {
  return {
    v: 1,
    t: T0,
    host: "claude",
    session: S,
    project: "tafwid",
    agent: null,
    phase: null,
    agentType: null,
    label: null,
    action: null,
    role: null,
    status: null,
    ...over,
  };
}

function run(over: Partial<RunEvent> = {}): RunEvent {
  return {
    v: 1,
    t: T0,
    event: "run",
    session: S,
    project: "tafwid",
    host: "claude",
    run: RUN,
    label: "Fix the parser",
    role: null,
    status: "working",
    ...over,
  };
}

function foldAll(events: WorldEvent[], from: LiveState = emptyLiveState()): LiveState {
  return events.reduce(fold, from);
}

const spawnPre = (over: Partial<HookEvent> = {}) =>
  hook({ event: "tool", phase: "pre", action: "spawn", ...over });

describe("fold: teams and coordinator", () => {
  it("creates a team and coordinator on the first event", () => {
    const state = fold(emptyLiveState(), hook({ event: "prompt" }));
    expect(Object.keys(state.teams)).toEqual([S]);
    expect(state.teams[S]).toEqual({
      id: S,
      project: "tafwid",
      host: "claude",
      accent: accentFor(S),
      lastEventAt: T0,
    });
    const coordinator = state.agents[S];
    expect(coordinator).toMatchObject({
      id: S,
      teamId: S,
      kind: "coordinator",
      role: "coordinator",
      name: nameFor(S),
      action: "thinking",
      status: "working",
      host: "claude",
      project: "tafwid",
      startedAt: T0,
      lastEventAt: T0,
      statusSince: T0,
    });
    expect(Object.keys(state.agents)).toHaveLength(1);
  });

  it("starts a session in the ready state until activity arrives", () => {
    const state = fold(emptyLiveState(), hook({ event: "session" }));
    expect(state.agents[S].status).toBe("ready");
  });

  it("maps an unknown host to claude and tolerates a missing project", () => {
    const state = fold(emptyLiveState(), hook({ event: "prompt", host: "unknown", project: null }));
    expect(state.agents[S].host).toBe("claude");
    expect(state.agents[S].project).toBe("");
    expect(state.teams[S].host).toBe("unknown");
  });

  it("keeps separate teams for separate sessions", () => {
    const state = foldAll([
      hook({ event: "prompt" }),
      hook({ event: "prompt", session: S2, project: "other", host: "codex" }),
    ]);
    expect(Object.keys(state.teams).sort()).toEqual([S, S2]);
    expect(state.agents[S2].host).toBe("codex");
    expect(state.teams[S].accent).toBe(accentFor(S));
  });
});

describe("fold: sub-agents and spawn matching", () => {
  it("creates a sub-agent with the label from the matching spawn", () => {
    const state = foldAll([
      hook({ event: "prompt" }),
      spawnPre({ t: T0 + 1, label: "Write the parser", agentType: "general-purpose" }),
      hook({ event: "subagent-start", t: T0 + 2, agent: SUB1, agentType: "general-purpose" }),
    ]);
    const sub = state.agents[SUB1];
    expect(sub).toMatchObject({
      id: SUB1,
      teamId: S,
      kind: "subagent",
      label: "Write the parser",
      role: "implementer",
      name: nameFor(SUB1),
      status: "working",
      action: "thinking",
      startedAt: T0 + 2,
      project: "tafwid",
    });
    expect(state.pendingSpawns).toEqual([]);
    // The parent shows the spawn gesture.
    expect(state.agents[S].action).toBe("spawn");
  });

  it("matches two spawns of the same type in order", () => {
    const state = foldAll([
      hook({ event: "prompt" }),
      spawnPre({ t: T0 + 1, label: "first job", agentType: "general-purpose" }),
      spawnPre({ t: T0 + 2, label: "second job", agentType: "general-purpose" }),
      hook({ event: "subagent-start", t: T0 + 3, agent: SUB1, agentType: "general-purpose" }),
      hook({ event: "subagent-start", t: T0 + 4, agent: SUB2, agentType: "general-purpose" }),
    ]);
    expect(state.agents[SUB1].label).toBe("first job");
    expect(state.agents[SUB2].label).toBe("second job");
  });

  it("prefers an exact agent type over an older spawn of another type", () => {
    const state = foldAll([
      hook({ event: "prompt" }),
      spawnPre({ t: T0 + 1, label: "explore job", agentType: "Explore" }),
      spawnPre({ t: T0 + 2, label: "review job", agentType: "code-reviewer" }),
      hook({ event: "subagent-start", t: T0 + 3, agent: SUB1, agentType: "code-reviewer" }),
    ]);
    expect(state.agents[SUB1].label).toBe("review job");
    expect(state.agents[SUB1].role).toBe("reviewer");
    expect(state.pendingSpawns.map((p) => p.label)).toEqual(["explore job"]);
  });

  it("lets a spawn with a null agent type match any start after exact matches", () => {
    const state = foldAll([
      hook({ event: "prompt", host: "codex" }),
      spawnPre({ t: T0 + 1, host: "codex", label: "codex job", agentType: null }),
      hook({ event: "subagent-start", t: T0 + 2, host: "codex", agent: SUB1, agentType: "worker" }),
    ]);
    expect(state.agents[SUB1].label).toBe("codex job");
    expect(state.agents[SUB1].host).toBe("codex");
    expect(state.pendingSpawns).toEqual([]);
  });

  it("uses an exact-type spawn before an older null-type spawn", () => {
    const state = foldAll([
      hook({ event: "prompt" }),
      spawnPre({ t: T0 + 1, label: "untyped job", agentType: null }),
      spawnPre({ t: T0 + 2, label: "worker job", agentType: "worker" }),
      hook({ event: "subagent-start", t: T0 + 3, agent: SUB1, agentType: "worker" }),
    ]);
    expect(state.agents[SUB1].label).toBe("worker job");
    expect(state.pendingSpawns.map((p) => p.label)).toEqual(["untyped job"]);
  });

  it("falls back to the agent type as the label when no spawn matches", () => {
    const state = foldAll([
      hook({ event: "prompt" }),
      spawnPre({ t: T0 + 1, label: "other job", agentType: "Explore" }),
      hook({ event: "subagent-start", t: T0 + 2, agent: SUB1, agentType: "code-reviewer" }),
    ]);
    expect(state.agents[SUB1].label).toBe("code-reviewer");
    expect(state.pendingSpawns).toHaveLength(1);
  });

  it("does not match a spawn from another session", () => {
    const state = foldAll([
      hook({ event: "prompt", session: S2 }),
      spawnPre({ t: T0 + 1, session: S2, label: "elsewhere", agentType: "general-purpose" }),
      hook({ event: "prompt" }),
      hook({ event: "subagent-start", t: T0 + 2, agent: SUB1, agentType: "general-purpose" }),
    ]);
    expect(state.agents[SUB1].label).toBe("general-purpose");
    expect(state.pendingSpawns).toHaveLength(1);
  });

  it("takes the role override from the spawn", () => {
    const state = foldAll([
      hook({ event: "prompt" }),
      spawnPre({ t: T0 + 1, label: "Check it", agentType: "general-purpose", role: "tester" }),
      hook({ event: "subagent-start", t: T0 + 2, agent: SUB1, agentType: "general-purpose" }),
    ]);
    expect(state.agents[SUB1].role).toBe("tester");
  });

  it("classifies the role from type and label without an override", () => {
    const state = foldAll([
      hook({ event: "prompt" }),
      spawnPre({ t: T0 + 1, label: "Update the README", agentType: "general-purpose" }),
      hook({ event: "subagent-start", t: T0 + 2, agent: SUB1, agentType: "general-purpose" }),
    ]);
    expect(state.agents[SUB1].role).toBe("documenter");
  });

  it("accepts a spawn from a sub-agent parent", () => {
    const state = foldAll([
      hook({ event: "prompt" }),
      hook({ event: "subagent-start", t: T0 + 1, agent: SUB1, agentType: "general-purpose" }),
      spawnPre({ t: T0 + 2, agent: SUB1, label: "nested", agentType: "Explore" }),
      hook({ event: "subagent-start", t: T0 + 3, agent: SUB2, agentType: "Explore" }),
    ]);
    expect(state.agents[SUB1].action).toBe("spawn");
    expect(state.agents[SUB2].label).toBe("nested");
    expect(state.agents[SUB2].teamId).toBe(S);
  });

  it("ignores an orphan subagent-stop", () => {
    const before = foldAll([hook({ event: "prompt" })]);
    const after = fold(
      before,
      hook({ event: "subagent-stop", t: T0 + 1, agent: SUB1, status: "done" }),
    );
    expect(after).toEqual(before);
    expect(fold(emptyLiveState(), hook({ event: "subagent-stop", agent: SUB1, status: "done" }))).toEqual(
      emptyLiveState(),
    );
  });
});

describe("fold: action, attention and ready", () => {
  it("sets the action from a tool event on the acting agent only", () => {
    const state = foldAll([
      hook({ event: "prompt" }),
      hook({ event: "subagent-start", t: T0 + 1, agent: SUB1, agentType: "general-purpose" }),
      hook({ event: "tool", phase: "pre", t: T0 + 2, agent: SUB1, action: "run-tests" }),
    ]);
    expect(state.agents[SUB1].action).toBe("run-tests");
    expect(state.agents[SUB1].lastEventAt).toBe(T0 + 2);
    expect(state.agents[S].action).toBe("thinking");
    const next = fold(state, hook({ event: "tool", phase: "post", t: T0 + 3, action: "edit-code" }));
    expect(next.agents[S].action).toBe("edit-code");
    expect(next.agents[SUB1].action).toBe("run-tests");
  });

  it("uses the other action when a tool event carries none", () => {
    const state = foldAll([hook({ event: "prompt" }), hook({ event: "tool", phase: "pre", t: T0 + 1 })]);
    expect(state.agents[S].action).toBe("other");
  });

  it("falls back to thinking after 10 s without a tool event", () => {
    const state = foldAll([
      hook({ event: "prompt" }),
      hook({ event: "tool", phase: "pre", t: T0 + 1, action: "edit-code" }),
    ]);
    expect(tick(state, T0 + 10).agents[S].action).toBe("edit-code");
    expect(tick(state, T0 + 11).agents[S].action).toBe("thinking");
    expect(tick(state, T0 + 11).agents[S].status).toBe("working");
  });

  it("gives attention for a permission event on the main agent", () => {
    const state = foldAll([
      hook({ event: "prompt" }),
      hook({ event: "permission", t: T0 + 5 }),
    ]);
    expect(state.agents[S].status).toBe("attention");
    expect(state.agents[S].statusSince).toBe(T0 + 5);
  });

  it("gives attention for a waiting notification on a sub-agent", () => {
    const state = foldAll([
      hook({ event: "prompt" }),
      hook({ event: "subagent-start", t: T0 + 1, agent: SUB1, agentType: "general-purpose" }),
      hook({ event: "notification", t: T0 + 2, agent: SUB1, status: "waiting" }),
    ]);
    expect(state.agents[SUB1].status).toBe("attention");
    expect(state.agents[S].status).toBe("working");
  });

  it("keeps attention from waiting as long as nothing else happens", () => {
    const state = foldAll([hook({ event: "prompt" }), hook({ event: "notification", t: T0 + 1, status: "waiting" })]);
    expect(tick(state, T0 + 600).agents[S].status).toBe("attention");
  });

  it("clears attention back to working on later activity", () => {
    const state = foldAll([
      hook({ event: "prompt" }),
      hook({ event: "permission", t: T0 + 1 }),
      hook({ event: "tool", phase: "pre", t: T0 + 20, action: "read" }),
    ]);
    expect(state.agents[S].status).toBe("working");
    expect(state.agents[S].statusSince).toBe(T0 + 20);
  });

  it("does not change statusSince when the status stays the same", () => {
    const state = foldAll([
      hook({ event: "prompt" }),
      hook({ event: "tool", phase: "pre", t: T0 + 5, action: "read" }),
    ]);
    expect(state.agents[S].statusSince).toBe(T0);
  });

  it("gives ready when the coordinator goes idle, and working again afterwards", () => {
    const idle = foldAll([hook({ event: "prompt" }), hook({ event: "stop", t: T0 + 30, status: "idle" })]);
    expect(idle.agents[S].status).toBe("ready");
    expect(idle.agents[S].statusSince).toBe(T0 + 30);
    const again = fold(idle, hook({ event: "prompt", t: T0 + 60 }));
    expect(again.agents[S].status).toBe("working");
  });

  it("does not touch the coordinator on sub-agent lifecycle events", () => {
    const state = foldAll([
      hook({ event: "prompt" }),
      hook({ event: "stop", t: T0 + 1, status: "idle" }),
      hook({ event: "subagent-start", t: T0 + 2, agent: SUB1, agentType: "general-purpose" }),
      hook({ event: "subagent-stop", t: T0 + 3, agent: SUB1, status: "done" }),
    ]);
    expect(state.agents[S].status).toBe("ready");
  });
});

describe("fold + tick: sub-agent endings", () => {
  const started = () =>
    foldAll([
      hook({ event: "prompt" }),
      hook({ event: "subagent-start", t: T0 + 1, agent: SUB1, agentType: "general-purpose" }),
    ]);

  it("marks a sub-agent done and removes it 20 s later", () => {
    const state = fold(started(), hook({ event: "subagent-stop", t: T0 + 100, agent: SUB1, status: "done" }));
    expect(state.agents[SUB1].status).toBe("done");
    expect(state.agents[SUB1].statusSince).toBe(T0 + 100);
    expect(tick(state, T0 + 119).agents[SUB1]).toBeDefined();
    const later = tick(state, T0 + 120);
    expect(later.agents[SUB1]).toBeUndefined();
    expect(later.agents[S]).toBeDefined();
  });

  for (const status of ["error", "interrupted"] as const) {
    it(`shows attention for ${status} and removes it after 2 min`, () => {
      const state = fold(started(), hook({ event: "subagent-stop", t: T0 + 100, agent: SUB1, status }));
      expect(state.agents[SUB1].status).toBe("attention");
      expect(tick(state, T0 + 100 + 119).agents[SUB1].status).toBe("attention");
      expect(tick(state, T0 + 100 + 120).agents[SUB1]).toBeUndefined();
    });
  }

  it("ignores later events for a finished sub-agent", () => {
    const stopped = fold(started(), hook({ event: "subagent-stop", t: T0 + 100, agent: SUB1, status: "done" }));
    const after = fold(stopped, hook({ event: "tool", phase: "pre", t: T0 + 101, agent: SUB1, action: "read" }));
    expect(after.agents[SUB1].status).toBe("done");
    expect(after.agents[SUB1].action).toBe("thinking");
    // A second stop does not extend the 20 s window.
    const twice = fold(after, hook({ event: "subagent-stop", t: T0 + 110, agent: SUB1, status: "done" }));
    expect(tick(twice, T0 + 120).agents[SUB1]).toBeUndefined();
  });
});

describe("tick: spawns, uncertainty and session end", () => {
  it("expires an unmatched spawn after 60 s", () => {
    const state = foldAll([
      hook({ event: "prompt" }),
      spawnPre({ t: T0 + 1, label: "lost", agentType: "general-purpose" }),
    ]);
    expect(tick(state, T0 + 60).pendingSpawns).toHaveLength(1);
    expect(tick(state, T0 + 61).pendingSpawns).toEqual([]);
  });

  it("gives uncertain after 5 min without events while working", () => {
    const state = foldAll([
      hook({ event: "prompt" }),
      hook({ event: "subagent-start", t: T0 + 1, agent: SUB1, agentType: "general-purpose" }),
    ]);
    expect(tick(state, T0 + 1 + 299).agents[SUB1].status).toBe("working");
    const dim = tick(state, T0 + 1 + 300);
    expect(dim.agents[SUB1].status).toBe("uncertain");
    expect(dim.agents[SUB1].statusSince).toBe(T0 + 301);
    const woken = fold(dim, hook({ event: "tool", phase: "pre", t: T0 + 400, agent: SUB1, action: "read" }));
    expect(woken.agents[SUB1].status).toBe("working");
  });

  it("does not dim a coordinator while its session has recent events", () => {
    const state = foldAll([
      hook({ event: "prompt" }),
      hook({ event: "subagent-start", t: T0 + 290, agent: SUB1, agentType: "general-purpose" }),
    ]);
    expect(tick(state, T0 + 310).agents[S].status).toBe("working");
    expect(tick(state, T0 + 290 + 300).agents[S].status).toBe("uncertain");
  });

  it("does not turn ready or attention into uncertain", () => {
    const ready = foldAll([hook({ event: "prompt" }), hook({ event: "stop", t: T0 + 1, status: "idle" })]);
    expect(tick(ready, T0 + 1000).agents[S].status).toBe("ready");
  });

  it("removes the team and its agents when the session ends", () => {
    const state = foldAll([
      hook({ event: "prompt" }),
      hook({ event: "prompt", session: S2, project: "other" }),
      spawnPre({ t: T0 + 1, label: "pending", agentType: "Explore" }),
      hook({ event: "subagent-start", t: T0 + 2, agent: SUB1, agentType: "general-purpose" }),
      run({ t: T0 + 3 }),
      spawnPre({ t: T0 + 4, session: S2, label: "keep", agentType: "Explore" }),
      hook({ event: "session-end", t: T0 + 5 }),
    ]);
    expect(Object.keys(state.teams)).toEqual([S2]);
    expect(Object.keys(state.agents)).toEqual([S2]);
    expect(state.pendingSpawns.map((p) => p.label)).toEqual(["keep"]);
  });

  it("records a tombstone for a session end even when the session is unknown", () => {
    const state = fold(emptyLiveState(), hook({ event: "session-end", t: T0 + 7 }));
    expect(state.teams).toEqual({});
    expect(state.agents).toEqual({});
    expect(state.ended).toEqual({ [S]: T0 + 7 });
  });

  it("ignores trailing events after session end and revives on a session event", () => {
    const ended = foldAll([
      hook({ event: "prompt" }),
      hook({ event: "session-end", t: T0 + 5 }),
    ]);
    expect(ended.ended).toEqual({ [S]: T0 + 5 });
    for (const trailing of [
      hook({ event: "stop", t: T0 + 6, status: "idle" }),
      hook({ event: "tool", phase: "post", t: T0 + 6, action: "read" }),
      hook({ event: "subagent-start", t: T0 + 6, agent: SUB1, agentType: "general-purpose" }),
      run({ t: T0 + 6 }),
    ]) {
      const after = fold(ended, trailing);
      expect(after.teams).toEqual({});
      expect(after.agents).toEqual({});
      expect(after).toBe(ended);
    }
    const revived = fold(ended, hook({ event: "session", t: T0 + 100 }));
    expect(revived.teams[S]).toBeDefined();
    expect(revived.agents[S].status).toBe("ready");
    expect(revived.ended).toEqual({});
    const working = fold(revived, hook({ event: "prompt", t: T0 + 101 }));
    expect(working.agents[S].status).toBe("working");
  });

  it("prunes ended-session tombstones after 30 min", () => {
    const state = fold(emptyLiveState(), hook({ event: "session-end", t: T0 }));
    expect(tick(state, T0 + 1799).ended).toEqual({ [S]: T0 });
    expect(tick(state, T0 + 1800).ended).toEqual({});
  });

  it("removes a team after 30 min of silence", () => {
    const state = foldAll([
      hook({ event: "prompt" }),
      hook({ event: "subagent-start", t: T0 + 1, agent: SUB1, agentType: "general-purpose" }),
      hook({ event: "prompt", session: S2, t: T0 + 1000 }),
    ]);
    const mid = tick(state, T0 + 1 + 1799);
    expect(mid.teams[S]).toBeDefined();
    const gone = tick(state, T0 + 1 + 1800);
    expect(gone.teams[S]).toBeUndefined();
    expect(gone.agents[S]).toBeUndefined();
    expect(gone.agents[SUB1]).toBeUndefined();
    expect(gone.teams[S2]).toBeDefined();
    expect(gone.agents[S2]).toBeDefined();
  });

  it("returns the same state object when nothing changes", () => {
    const state = foldAll([hook({ event: "prompt" })]);
    expect(tick(state, T0 + 1)).toBe(state);
  });
});

describe("fold: delegated runs", () => {
  it("joins the owning team as a delegated agent", () => {
    const base = foldAll([hook({ event: "prompt" })]);
    const state = fold(base, run({ t: T0 + 1 }));
    expect(state.agents[RUN]).toMatchObject({
      id: RUN,
      teamId: S,
      kind: "delegated",
      role: "implementer",
      name: nameFor(RUN),
      label: "Fix the parser",
      status: "working",
      host: "claude",
      project: "tafwid",
      startedAt: T0 + 1,
    });
    expect(Object.keys(state.teams)).toEqual([S]);
    expect(state.teams[S].lastEventAt).toBe(T0 + 1);
  });

  it("creates the team when it is missing", () => {
    const state = fold(emptyLiveState(), run({ session: S2, project: "elsewhere", host: "codex" }));
    expect(state.teams[S2]).toMatchObject({ id: S2, project: "elsewhere", host: "codex", accent: accentFor(S2) });
    expect(state.agents[RUN].teamId).toBe(S2);
    expect(state.agents[RUN].host).toBe("codex");
  });

  it("takes the role from the event", () => {
    const state = fold(emptyLiveState(), run({ role: "reviewer" }));
    expect(state.agents[RUN].role).toBe("reviewer");
  });

  it("updates status and leaves 20 s after done", () => {
    const working = fold(emptyLiveState(), run({ t: T0 }));
    const attention = fold(working, run({ t: T0 + 5, status: "attention" }));
    expect(attention.agents[RUN].status).toBe("attention");
    expect(attention.agents[RUN].startedAt).toBe(T0);
    expect(attention.agents[RUN].finishedAt).toBe(T0 + 5);
    const done = fold(attention, run({ t: T0 + 10, status: "done" }));
    expect(done.agents[RUN].status).toBe("done");
    expect(tick(done, T0 + 29).agents[RUN]).toBeDefined();
    expect(tick(done, T0 + 30).agents[RUN]).toBeUndefined();
  });
});

describe("fold: delegated run attention", () => {
  it("is terminal and removed 2 min later, like a sub-agent error", () => {
    const state = fold(fold(emptyLiveState(), run({ t: T0 })), run({ t: T0 + 10, status: "attention" }));
    expect(state.agents[RUN].status).toBe("attention");
    expect(tick(state, T0 + 10 + 119).agents[RUN].status).toBe("attention");
    expect(tick(state, T0 + 10 + 120).agents[RUN]).toBeUndefined();
  });

  it("does not extend the window on repeated attention events", () => {
    const first = fold(emptyLiveState(), run({ t: T0, status: "attention" }));
    const again = fold(first, run({ t: T0 + 60, status: "attention" }));
    expect(tick(again, T0 + 120).agents[RUN]).toBeUndefined();
  });

  it("is cleared by a later working event", () => {
    const attention = fold(emptyLiveState(), run({ t: T0, status: "attention" }));
    const revived = fold(attention, run({ t: T0 + 30, status: "working" }));
    expect(revived.agents[RUN].status).toBe("working");
    expect(revived.agents[RUN].finishedAt).toBeUndefined();
    expect(revived.agents[RUN].startedAt).toBe(T0);
    expect(tick(revived, T0 + 30 + 200).agents[RUN]).toBeDefined();
  });

  it("still lets a done run leave after 20 s and ignores later events", () => {
    const done = fold(emptyLiveState(), run({ t: T0, status: "done" }));
    expect(fold(done, run({ t: T0 + 5, status: "working" }))).toBe(done);
    expect(tick(done, T0 + 19).agents[RUN]).toBeDefined();
    expect(tick(done, T0 + 20).agents[RUN]).toBeUndefined();
  });
});

describe("fold: spawn expiry follows event time", () => {
  it("does not attach a stale spawn label when no tick ran in between", () => {
    const state = foldAll([
      hook({ event: "prompt" }),
      spawnPre({ t: T0 + 1, label: "stale job", agentType: "general-purpose" }),
      hook({ event: "subagent-start", t: T0 + 91, agent: SUB1, agentType: "general-purpose" }),
    ]);
    expect(state.agents[SUB1].label).toBe("general-purpose");
    expect(state.pendingSpawns).toEqual([]);
  });

  it("still matches a spawn just inside the window and prunes expired ones", () => {
    const state = foldAll([
      hook({ event: "prompt" }),
      spawnPre({ t: T0 + 1, label: "old", agentType: "Explore" }),
      spawnPre({ t: T0 + 50, label: "fresh", agentType: "general-purpose" }),
      hook({ event: "subagent-start", t: T0 + 60, agent: SUB1, agentType: "general-purpose" }),
    ]);
    expect(state.agents[SUB1].label).toBe("fresh");
    expect(state.pendingSpawns.map((p) => p.label)).toEqual(["old"]);
    const later = fold(
      state,
      hook({ event: "subagent-start", t: T0 + 61, agent: SUB2, agentType: "Explore" }),
    );
    expect(later.agents[SUB2].label).toBe("Explore");
    expect(later.pendingSpawns).toEqual([]);
  });
});

describe("fold: purity", () => {
  it("does not mutate its input and keeps state JSON-serialisable", () => {
    const base = foldAll([
      hook({ event: "prompt" }),
      spawnPre({ t: T0 + 1, label: "job", agentType: "general-purpose" }),
    ]);
    const snapshot = JSON.stringify(base);
    const next = fold(base, hook({ event: "subagent-start", t: T0 + 2, agent: SUB1, agentType: "general-purpose" }));
    tick(next, T0 + 100000);
    tick(base, T0 + 100000);
    expect(JSON.stringify(base)).toBe(snapshot);
    expect(JSON.parse(JSON.stringify(next))).toEqual(next);
  });
});

describe("nameFor and accentFor", () => {
  it("is deterministic and drawn from a fixed list", () => {
    expect(nameFor(SUB1)).toBe(nameFor(SUB1));
    const names = new Set<string>();
    for (let i = 0; i < 500; i += 1) names.add(nameFor(i.toString(16).padStart(16, "0")));
    expect(names.size).toBeGreaterThanOrEqual(24);
    for (const name of names) expect(name).toMatch(/^[A-Z][a-z]{1,9}$/);
  });

  it("returns accent hex colours from a palette of at least 8", () => {
    expect(accentFor(S)).toBe(accentFor(S));
    const accents = new Set<string>();
    for (let i = 0; i < 500; i += 1) accents.add(accentFor(i.toString(16).padStart(16, "0")));
    expect(accents.size).toBeGreaterThanOrEqual(8);
    for (const accent of accents) expect(accent).toMatch(/^#[0-9a-f]{6}$/);
  });
});
